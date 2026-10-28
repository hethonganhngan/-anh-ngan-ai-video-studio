"""B10/B11: lịch đăng nhiều nền tảng, CSV import, insights A10, export CSV, chặn xuất bản khi chưa duyệt."""
from tests.helpers import create_project, full_scores


def _approved(login, channels, topic):
    pm, qc = login("pm"), login("qc")
    p = create_project(pm, channels["KTMB"]["id"], topic=topic, duration_sec=8)
    pid = p["id"]
    pm.post(f"/projects/{pid}/script/ideas")
    pm.post(f"/projects/{pid}/script/write")
    pm.post(f"/projects/{pid}/script/approve", json={})
    pm.post(f"/projects/{pid}/validate-assets")
    pm.post(f"/projects/{pid}/generate", json={})
    q = qc.get(f"/projects/{pid}/qc").json()
    scores = full_scores(10, {"audio": q["agent_final"]["scores"]["audio"]["score"], "visual": q["agent_final"]["scores"]["visual"]["score"]})
    assert qc.post(f"/projects/{pid}/qc/final", json={"scores": scores}).json()["result"] == "PASS"
    assert pm.post(f"/projects/{pid}/approve", json={"decision": "APPROVED", "comment": "ok"}).status_code == 200
    return pid


def test_unapproved_video_cannot_be_scheduled(login, channels):
    pm, pub = login("pm"), login("publisher")
    p = create_project(pm, channels["KTMB"]["id"], topic="Chưa duyệt không được đăng", duration_sec=8)
    r = pub.post("/publications", json={"project_id": p["id"], "platform": "TIKTOK", "caption": "abc"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "NOT_APPROVED"


def test_multi_platform_csv_insights_export(login, channels):
    pub, pm = login("publisher"), login("pm")
    a = _approved(login, channels, "Dấu hiệu bé mọc răng")
    b = _approved(login, channels, "Lịch tắm nắng cho bé")
    # Kênh KTMB không có ZALO
    r = pub.post("/publications", json={"project_id": a, "platform": "ZALO", "caption": "x"})
    assert r.status_code == 422
    urls = {}
    for pid, plat, url in ((a, "TIKTOK", "https://www.tiktok.com/@ktmb/video/1"), (a, "YOUTUBE", "https://youtube.com/shorts/abc"),
                           (b, "FACEBOOK", "https://www.facebook.com/ktmb/videos/2")):
        x = pub.post("/publications", json={"project_id": pid, "platform": plat, "caption": "Kiến thức có nguồn — tham khảo bác sĩ"}).json()
        assert pub.post(f"/publications/{x['id']}/mark-published", json={"post_url": url}).status_code == 200
        urls[url] = x["id"]
    csv_body = ("post_url,captured_at,views,likes,comments,shares,saves,retention_rate,conversions\n"
                "https://www.tiktok.com/@ktmb/video/1,2026-10-28T10:00:00,5000,400,50,30,20,35.5,4\n"
                "https://youtube.com/shorts/abc,2026-10-28T10:00:00,800,20,2,1,0,,\n"
                "https://www.facebook.com/ktmb/videos/2,2026-10-28T10:00:00,1500,90,9,12,3,40,1\n"
                "https://www.facebook.com/khong-ton-tai,2026-10-28T10:00:00,10,1,0,0,0,,\n"
                "https://www.tiktok.com/@ktmb/video/1,2026-10-28T11:00:00,-5,0,0,0,0,,\n")
    r = pm.post("/analytics/import", files={"file": ("data.csv", csv_body.encode(), "text/csv")})
    assert r.status_code == 403  # PM không có analytics.enter
    r = pub.post("/analytics/import", files={"file": ("data.csv", csv_body.encode(), "text/csv")}).json()
    assert r["imported"] == 3 and len(r["errors"]) == 2
    perf = {x["post_url"]: x for x in pm.get("/analytics/performance").json()}
    tt = perf["https://www.tiktok.com/@ktmb/video/1"]
    assert tt["views"] == 5000 and tt["engagement_rate"] == 10.0 and tt["conversions"] == 4
    assert perf["https://youtube.com/shorts/abc"]["retention_rate"] is None
    ins = pm.get(f"/analytics/insights?channel_id={channels['KTMB']['id']}").json()
    assert any("Trung vị lượt xem: 1.500" in i or "Trung vị lượt xem: 1,500" in i for i in ins["insights"])
    assert ins["median_views"] == 1500 and ins["anomalies"] == []  # 800 không < 50% trung vị
    csv_out = pm.get("/analytics/export.csv")
    assert csv_out.status_code == 200 and "engagement_rate" in csv_out.text and "tiktok.com" in csv_out.text
    cal = pub.get("/publications/calendar").json()
    assert {x["platform"] for x in cal if x["project_id"] in (a, b)} >= {"TIKTOK", "YOUTUBE", "FACEBOOK"}
    d = login("viewer").get(f"/dashboard?channel_id={channels['KTMB']['id']}").json()
    k = {x["key"]: x for x in d["kpis"]}
    assert k["views_total"]["value"] >= 7300 and k["published"]["value"] >= 2
