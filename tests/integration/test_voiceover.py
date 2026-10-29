"""Voice-over TTS (M06): DEMO dùng Mock TTS → 1 track âm thanh khớp timeline, ghi chi phí mô phỏng, render có giọng."""
from tests.helpers import create_project, to_scene_qc


def test_generate_voiceover_demo(login, channels):
    pm = login("pm")
    v = pm.post("/voices", json={"name": "Giọng tư vấn AI", "accent": "Miền Trung", "tone": "ấm áp",
                                 "provider_code": "gemini_tts", "provider_voice_id": "Kore",
                                 "consent_status": "GRANTED", "usage_rights": "Giọng AI dựng sẵn của Google"}).json()
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Sữa cho bé biếng ăn", duration_sec=16,
                       voice_profile_id=v["id"])
    pid = p["id"]
    to_scene_qc(pm, pid)

    r = pm.post(f"/projects/{pid}/voiceover/generate", json={"scene_volume": 0.3})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["simulated"] is True and res["provider"] == "mock_tts"
    assert len(res["segments"]) == 2 and res["segments"][1]["start"] > 0
    tl = res["timeline"]
    assert len(tl["voiceover"]) == 1 and tl["voiceover"][0]["asset_id"] == res["asset_id"]
    assert all(c["volume"] == 0.3 for c in tl["clips"])
    a = pm.get(f"/assets/{res['asset_id']}").json()
    assert a["asset_type"] == "AUDIO" and "tts" in a["tags"]

    # Tạo lại → thay track cũ, không cộng dồn
    res2 = pm.post(f"/projects/{pid}/voiceover/generate", json={}).json()
    assert len(res2["timeline"]["voiceover"]) == 1 and res2["asset_id"] != res["asset_id"]
    assert pm.get(f"/projects/{pid}/timeline").json()["voiceover"][0]["asset_id"] == res2["asset_id"]


def test_voiceover_requires_voice_profile(login, channels):
    pm = login("pm")
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Không có giọng", duration_sec=8)
    to_scene_qc(pm, p["id"])
    r = pm.post(f"/projects/{p['id']}/voiceover/generate", json={})
    assert r.status_code == 404
