"""Luồng nghiệp vụ đầy đủ: tạo dự án → kịch bản → storyboard → tạo cảnh Mock → QC cảnh → render MP4 thật
→ QC 10 tiêu chí → phê duyệt → lịch đăng → xuất file → đánh dấu đăng → analytics → dashboard."""
from tests.helpers import create_project, full_scores, make_png, upload


def test_full_pipeline(login, channels):
    pm, qc, pub, admin = login("pm"), login("qc"), login("publisher"), login("admin")
    ch = channels["ANNGAN"]
    logo = upload(pm, make_png("logo.png"), "LOGO", channel_id=ch["id"], usage_rights="OWNED", tags="logo")
    assert logo.status_code == 201, logo.text

    p = create_project(pm, ch["id"], topic="Cách chọn sữa cho bé trên 2 tuổi tại Ánh Ngân", duration_sec=16,
                       cta="Ghé Ánh Ngân để được tư vấn nhé", budget_limit=500000)
    pid = p["id"]
    assert p["status"] == "CREATED" and p["data_mode"] == "DEMO"

    # M03: 3 ý tưởng có điểm, tự chọn ý tưởng tốt nhất (ASSISTED)
    r = pm.post(f"/projects/{pid}/script/ideas").json()
    assert len(r["script"]["ideas"]) == 3
    assert all("score" in i and "scores" in i for i in r["script"]["ideas"])
    assert r["script"]["selected_idea_index"] is not None
    assert r["project"]["status"] == "SCRIPT_GENERATING"

    r = pm.post(f"/projects/{pid}/script/write").json()
    assert r["project"]["status"] == "SCRIPT_REVIEW"
    assert len(r["scenes"]) == 2  # 16s / 8s
    for s in r["scenes"]:
        assert s["duration_sec"] == 8 and len(s["dialogue"]) <= 2
    assert r["current"]["version_no"] == 1 and r["check"]["errors"] == []

    # Chỉnh sửa → phiên bản 2 (bất biến v1)
    edited = dict(title=r["current"]["title"], hook=r["current"]["hook"], body=r["current"]["body"], cta=r["current"]["cta"],
                  scenes=[{k: s[k] for k in ("title", "scene_type", "action", "dialogue", "setting", "camera", "lighting",
                                             "sound", "duration_sec")} for s in r["scenes"]], note="Sửa câu chữ")
    edited["scenes"][0]["dialogue"][0]["text"] = "Mẹ ơi, bé hơn 2 tuổi nên chọn sữa thế nào?"
    r = pm.put(f"/projects/{pid}/script", json=edited).json()
    assert r["current"]["version_no"] == 2 and len(r["versions"]) == 2

    # Duyệt kịch bản → STORYBOARD_READY và prompt 9 phần
    r = pm.post(f"/projects/{pid}/script/approve", json={"comment": "Đạt"}).json()
    assert r["project"]["status"] == "STORYBOARD_READY"
    for s in r["scenes"]:
        for part in ("[1. LOẠI CẢNH]", "[2. NHÂN VẬT]", "[3. HÀNH ĐỘNG]", "[4. BỐI CẢNH]", "[5. MÁY QUAY]", "[6. ÁNH SÁNG]",
                     "[7. ÂM THANH]", "[8. THOẠI]", "[9. NEGATIVE PROMPT]"):
            assert part in s["prompt_text"]

    # M05: kiểm tra tài nguyên → tạo cảnh Mock (eager) → QC cảnh → auto render (ASSISTED) → FINAL_QC
    rep = pm.post(f"/projects/{pid}/validate-assets").json()
    assert rep["blocking"] == []
    jobs = pm.post(f"/projects/{pid}/generate", json={}).json()
    assert len(jobs) == 2
    ov = pm.get(f"/projects/{pid}/overview").json()
    assert ov["project"]["status"] == "FINAL_QC", [(e["to_status"], e["note"]) for e in ov["events"]][-4:]
    assert all(s["status"] == "QC_PASSED" for s in ov["scenes"])
    assert ov["renders"] and ov["cost_total"] == 24000  # 2 cảnh x 8s x 1500 VND (mô phỏng)

    # MP4 thật
    qcv = qc.get(f"/projects/{pid}/qc").json()
    render = qcv["render"]
    assert render["width"] == 540 and render["height"] == 960 and 15.5 < render["duration_sec"] < 16.5
    assert render["probe"]["has_audio"] and render["thumbnail_asset_id"] and render["subtitle_asset_id"]
    video = pm.get(f"/assets/{render['video_asset_id']}/content")
    assert video.status_code == 200 and video.content[4:8] == b"ftyp"
    srt = pm.get(f"/assets/{render['subtitle_asset_id']}/content").text
    assert "-->" in srt and "Mẹ ơi" in srt

    agent = qcv["agent_final"]
    assert agent["reviewer_type"] == "AGENT" and set(agent["pending_manual"]) >= {"character", "voice", "lipsync"}

    # M07: QC thủ công < 98 → không đạt
    r = qc.post(f"/projects/{pid}/qc/final", json={"scores": full_scores(9), "notes": "Chưa đạt"})
    assert r.status_code == 200 and r.json()["result"] == "FAIL"
    assert qc.get(f"/projects/{pid}").json()["status"] == "FINAL_QC"
    # Phê duyệt khi chưa đạt → bị chặn
    assert pm.post(f"/projects/{pid}/approve", json={"decision": "APPROVED"}).status_code == 409

    r = qc.post(f"/projects/{pid}/qc/final", json={"scores": full_scores(10, {"lipsync": 9}), "notes": "Đạt 99"})
    assert r.json()["result"] == "PASS" and r.json()["total_score"] == 99
    assert qc.get(f"/projects/{pid}").json()["status"] == "APPROVAL_PENDING"

    # Người không có quyền không phê duyệt được
    assert qc.post(f"/projects/{pid}/approve", json={"decision": "APPROVED"}).status_code == 403
    assert pub.post(f"/projects/{pid}/approve", json={"decision": "APPROVED"}).status_code == 403
    r = pm.post(f"/projects/{pid}/approve", json={"decision": "APPROVED", "comment": "Phát hành"})
    assert r.status_code == 200, r.text
    assert pm.get(f"/projects/{pid}").json()["status"] == "APPROVED"

    # M10: lịch đăng, caption bị bộ lọc tuân thủ chặn
    bad = pub.post("/publications", json={"project_id": pid, "platform": "FACEBOOK", "caption": "Sữa tốt nhất cho bé"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "CAPTION_COMPLIANCE"
    pb = pub.post("/publications", json={"project_id": pid, "platform": "FACEBOOK", "caption": "Ánh Ngân đồng hành cùng mẹ",
                                         "hashtags": ["anhngan", "mevabe"], "scheduled_at": "2026-11-01T11:00:00Z"})
    assert pb.status_code == 201, pb.text
    pub_id = pb.json()["id"]
    assert pb.json()["status"] == "SCHEDULED" and pb.json()["hashtags"] == ["#anhngan", "#mevabe"]
    cal = pub.get("/publications/calendar").json()
    assert any(x["id"] == pub_id for x in cal)

    # DEMO không được tự động xuất bản
    r = pub.post(f"/publications/{pub_id}/publish-api")
    assert r.status_code == 422 and r.json()["error"]["code"] == "DEMO_AUTO_PUBLISH_BLOCKED"
    # Xuất file đăng thủ công
    ex = pub.post(f"/publications/{pub_id}/export").json()
    z = pub.get(f"/assets/{ex['asset_id']}/content").content
    assert z[:2] == b"PK"
    assert pm.get(f"/projects/{pid}").json()["status"] == "PUBLISH_QUEUED"
    # URL sai nền tảng
    assert pub.post(f"/publications/{pub_id}/mark-published", json={"post_url": "https://tiktok.com/@a/1"}).status_code == 422
    r = pub.post(f"/publications/{pub_id}/mark-published", json={"post_url": "https://www.facebook.com/anhngan/videos/123"})
    assert r.status_code == 200 and r.json()["status"] == "PUBLISHED"
    assert pm.get(f"/projects/{pid}").json()["status"] == "PUBLISHED"

    # Analytics
    r = pub.post(f"/publications/{pub_id}/snapshots", json={"views": 1200, "likes": 80, "comments": 12, "shares": 9,
                                                            "retention_rate": 41.5, "conversions": 3})
    assert r.status_code == 201, r.text
    assert pm.get(f"/projects/{pid}").json()["status"] == "ANALYTICS_COLLECTION"
    assert pub.post(f"/publications/{pub_id}/snapshots", json={"views": 100}).json()["error"]["code"] == "METRIC_DECREASED"
    perf = pm.get("/analytics/performance").json()
    row = next(x for x in perf if x["publication_id"] == pub_id)
    assert row["engagement_rate"] == round((80 + 12 + 9) / 1200 * 100, 2) and row["cost"] == 24000
    assert row["cost_per_1k_views"] == 20000

    # Dashboard CEO: KPI có công thức và nguồn
    d = admin.get("/dashboard").json()
    for k in d["kpis"]:
        assert k["formula"] and k["source"]
    keys = {k["key"]: k for k in d["kpis"]}
    assert keys["published"]["value"] >= 1 and keys["cost_total"]["value"] >= 24000
    assert keys["avg_qc"]["value"] is not None

    # Lịch sử workflow đủ các bước chính
    statuses = [e["to_status"] for e in pm.get(f"/projects/{pid}/events").json()]
    for st in ["CREATED", "SCRIPT_GENERATING", "SCRIPT_REVIEW", "STORYBOARD_READY", "ASSET_VALIDATION", "GENERATION_QUEUED",
               "GENERATING", "SCENE_QC", "RENDERING", "FINAL_QC", "APPROVAL_PENDING", "APPROVED", "PUBLISH_QUEUED",
               "PUBLISHED", "ANALYTICS_COLLECTION"]:
        assert st in statuses, st
