"""Chế độ AUTO (D19): một lần chạy AI Director từ chủ đề → video hoàn chỉnh (FINAL_QC) — tự duyệt kịch bản sạch,
tự lồng giọng Voice Profile (M04); kịch bản vi phạm tuân thủ CRITICAL thì dừng ở cổng chờ người duyệt."""
from tests.helpers import create_project, make_video


def _voice(pm) -> str:
    return pm.post("/voices", json={"name": "Giọng AI miền Nam", "accent": "Miền Nam", "tone": "ấm áp",
                                    "provider_code": "gemini_tts", "provider_voice_id": "Kore",
                                    "consent_status": "GRANTED", "usage_rights": "Giọng AI dựng sẵn của Google"}).json()["id"]


def test_auto_runs_topic_to_final_video_with_voiceover(login, channels):
    pm = login("pm")
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Bé trên 2 tuổi nên uống sữa gì", duration_sec=16,
                       automation_level="AUTO", voice_profile_id=_voice(pm))
    r = pm.post(f"/projects/{p['id']}/advance")
    assert r.status_code == 200, r.text
    assert "Tự duyệt kịch bản (AUTO)" in r.json()["steps"]

    ov = pm.get(f"/projects/{p['id']}/overview").json()
    assert ov["project"]["status"] == "FINAL_QC", [(e["to_status"], e["note"]) for e in ov["events"]][-5:]
    assert ov["renders"]
    tl = pm.get(f"/projects/{p['id']}/timeline").json()
    tl = tl.get("timeline", tl)
    assert tl["voiceover"] and all(c["volume"] == 0.35 for c in tl["clips"])  # giọng M04 lồng, tiếng cảnh hạ nền
    script = pm.get(f"/projects/{p['id']}/script").json()["script"]
    assert script["status"] == "APPROVED"


def test_auto_stops_at_review_when_script_violates_compliance(login, channels):
    pm = login("pm")
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Kịch bản AUTO có câu vi phạm", duration_sec=8,
                       automation_level="AUTO")
    pid = p["id"]
    pm.post(f"/projects/{pid}/script/ideas")
    view = pm.post(f"/projects/{pid}/script/write").json()
    cur = view["current"]
    scenes = [{k: s[k] for k in ("title", "scene_type", "action", "dialogue", "setting", "camera", "lighting", "sound", "duration_sec")}
              for s in view["scenes"]]
    scenes[0]["dialogue"] = [{"speaker": "Chị Ngân", "text": "Sản phẩm giúp chữa biếng ăn cho bé"}]
    pm.put(f"/projects/{pid}/script", json={"title": cur["title"], "hook": cur["hook"], "body": cur["body"], "cta": cur["cta"],
                                            "scenes": scenes, "note": "câu vi phạm"})
    r = pm.post(f"/projects/{pid}/advance").json()
    assert r["status"] == "SCRIPT_REVIEW" and any(s.startswith("Dừng") for s in r["steps"]), r
    assert pm.get(f"/projects/{pid}/script").json()["script"]["status"] != "APPROVED"


def test_replacing_scene_clip_after_final_rerenders_with_new_clip(login, channels):
    """Hồi quy: dự án đã có timeline → nhập clip mới cho cảnh thì bản dựng lại phải dùng clip mới, không giữ clip cũ."""
    pm, editor = login("pm"), login("editor")
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Thay clip sau khi dựng", duration_sec=8,
                       automation_level="AUTO", voice_profile_id=_voice(pm))
    pm.post(f"/projects/{p['id']}/advance")
    assert pm.get(f"/projects/{p['id']}").json()["status"] == "FINAL_QC"
    scene = pm.get(f"/projects/{p['id']}/script").json()["scenes"][0]
    old_asset = pm.get(f"/projects/{p['id']}/timeline").json()
    old_asset = old_asset.get("timeline", old_asset)["clips"][0]["asset_id"]
    renders_before = len(pm.get(f"/projects/{p['id']}/overview").json()["renders"])

    with open(make_video("flow_new.mp4", 720, 1280, 8), "rb") as f:
        r = editor.post(f"/scenes/{scene['id']}/import-flow", files={"file": ("flow_new.mp4", f)})
    assert r.status_code == 200, r.text
    tl = pm.get(f"/projects/{p['id']}/timeline").json()
    tl = tl.get("timeline", tl)
    assert tl["clips"][0]["asset_id"] == r.json()["asset_id"] != old_asset
    ov = pm.get(f"/projects/{p['id']}/overview").json()
    assert ov["project"]["status"] == "FINAL_QC" and len(ov["renders"]) > renders_before
