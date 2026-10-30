"""M06 Editor + B06 Render + B07 QC: timeline đầy đủ, MP4 thật, chấm 10 tiêu chí, xử lý lỗi QC, phê duyệt."""
import pytest

from tests.helpers import create_project, full_scores, make_audio, make_png, upload


def _to_scene_qc(pm, ch, topic, duration=16):
    p = create_project(pm, ch, topic=topic, duration_sec=duration, automation_level="MANUAL")
    pid = p["id"]
    pm.post(f"/projects/{pid}/script/ideas")
    pm.post(f"/projects/{pid}/script/select-idea", json={"index": 0})
    pm.post(f"/projects/{pid}/script/write")
    pm.post(f"/projects/{pid}/script/approve", json={})
    pm.post(f"/projects/{pid}/validate-assets")
    pm.post(f"/projects/{pid}/generate", json={})
    assert pm.get(f"/projects/{pid}").json()["status"] == "SCENE_QC"
    return pid


def test_editor_timeline_full_render(login, channels):
    pm, editor = login("pm"), login("editor")
    ch = channels["BPCD"]["id"]
    pid = _to_scene_qc(pm, ch, "Ba Phi kể chuyện tiết kiệm")
    tl = editor.get(f"/projects/{pid}/timeline").json()
    assert len(tl["clips"]) == 2 and tl["subtitles"]["enabled"]
    vo = upload(editor, make_audio("vo.mp3", 4, 660), "AUDIO", usage_rights="CONSENTED").json()
    music = upload(editor, make_audio("bgm.mp3", 5, 330), "AUDIO", usage_rights="LICENSED").json()
    logo = upload(editor, make_png("logo.png"), "LOGO", channel_id=ch, usage_rights="OWNED").json()

    tl["clips"] = list(reversed(tl["clips"]))  # đổi thứ tự cảnh
    tl["clips"][0]["trim_start"], tl["clips"][0]["trim_end"] = 1.0, 6.0  # cắt còn 5s
    bad = {**tl, "clips": [{**tl["clips"][0], "trim_end": 50}]}
    r = editor.put(f"/projects/{pid}/timeline", json=bad)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_TRIM"
    tl["voiceover"] = [{"asset_id": vo["id"], "start": 1.0, "volume": 1.0}]
    tl["music"] = {"asset_id": music["id"], "volume": 0.2, "fade_out": 1.5}
    tl["logo"] = {"asset_id": logo["id"], "position": "top_right", "scale": 0.2, "opacity": 0.9}
    tl["thumbnail"] = {"time_sec": 1.0, "title": "Ba Phi tiết kiệm"}
    r = editor.put(f"/projects/{pid}/timeline", json=tl)
    assert r.status_code == 200, r.text
    # Người xem không sửa được timeline
    assert login("viewer").put(f"/projects/{pid}/timeline", json=tl).status_code == 403

    job = editor.post(f"/projects/{pid}/render").json()
    assert job["status"] in ("QUEUED", "SUCCEEDED")
    renders = editor.get(f"/projects/{pid}/renders").json()
    assert len(renders) == 1
    r0 = renders[0]
    assert 12.5 < r0["duration_sec"] < 13.5  # 5s + 8s
    assert r0["probe"]["has_audio"] and r0["thumbnail_asset_id"]
    assert pm.get(f"/projects/{pid}").json()["status"] == "FINAL_QC"
    q = login("qc").get(f"/projects/{pid}/qc").json()
    assert q["agent_final"]["scores"]["brand"]["evidence"]["logo"] is True
    jobs = editor.get(f"/render-jobs?project_id={pid}").json()
    assert jobs[0]["status"] == "SUCCEEDED"


@pytest.mark.slow
def test_render_real_1080p(login, channels, monkeypatch):
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "output_width", 1080)
    monkeypatch.setattr(s, "output_height", 1920)
    monkeypatch.setattr(s, "mock_video_width", 1080)
    monkeypatch.setattr(s, "mock_video_height", 1920)
    pm = login("pm")
    pid = _to_scene_qc(pm, channels["ANNGAN"]["id"], "Render 1080p thật", duration=8)
    pm.post(f"/projects/{pid}/render")
    r = pm.get(f"/projects/{pid}/renders").json()[0]
    assert (r["width"], r["height"]) == (1080, 1920) and r["probe"]["fps"] == 30.0
    assert r["probe"]["video_codec"] == "h264" and r["probe"]["audio_codec"] == "aac"
    q = pm.get(f"/projects/{pid}/qc").json()
    assert q["agent_final"]["scores"]["visual"]["score"] == 10


def test_scene_qc_human_fail_blocks_render(login, channels):
    pm, qc = login("pm"), login("qc")
    pid = _to_scene_qc(pm, channels["ANNGAN"]["id"], "QC cảnh thủ công")
    scenes = pm.get(f"/projects/{pid}/script").json()["scenes"]
    r = qc.post(f"/scenes/{scenes[1]['id']}/qc", json={"passed": False, "notes": "Khuôn mặt nhân vật đổi", "criterion": "character"})
    assert r.status_code == 200
    r = pm.post(f"/projects/{pid}/render")
    assert r.status_code == 422 and r.json()["error"]["code"] == "SCENE_QC_FAILED"
    # Tạo lại cảnh lỗi → QC tự động → render được
    assert pm.post(f"/scenes/{scenes[1]['id']}/regenerate").status_code == 200
    assert pm.post(f"/projects/{pid}/render").status_code == 200
    assert pm.get(f"/projects/{pid}").json()["status"] == "FINAL_QC"


def test_final_qc_rules_and_approval(login, channels):
    pm, qc, admin = login("pm"), login("qc"), login("admin")
    pid = _to_scene_qc(pm, channels["ANNGAN"]["id"], "QC tổng thể và phê duyệt")
    pm.post(f"/projects/{pid}/render")
    q = qc.get(f"/projects/{pid}/qc").json()
    auto_audio = q["agent_final"]["scores"]["audio"]["score"]
    # Thiếu tiêu chí
    r = qc.post(f"/projects/{pid}/qc/final", json={"scores": {"hook": {"score": 10}}, "notes": ""})
    assert r.status_code == 422 and r.json()["error"]["code"] == "QC_INCOMPLETE"
    # AUTO không được vượt điểm máy đo
    if auto_audio < 10:
        r = qc.post(f"/projects/{pid}/qc/final", json={"scores": full_scores(10), "notes": ""})
        assert r.json()["error"]["code"] == "QC_AUTO_OVERRIDE"
    # Có lỗi CRITICAL mới → không đạt dù điểm cao
    scores = full_scores(10, {"audio": auto_audio})
    r = qc.post(f"/projects/{pid}/qc/final", json={"scores": scores, "notes": "",
                                                   "findings": [{"criterion": "compliance", "severity": "CRITICAL",
                                                                 "description": "Caption nhắc tuổi dưới 24 tháng"}]})
    assert r.json()["result"] == "FAIL"
    f = next(x for x in qc.get(f"/projects/{pid}/qc").json()["findings"] if x["severity"] == "CRITICAL")
    r = qc.post(f"/qc-findings/{f['id']}/resolve", json={"action": "WAIVE", "note": "bỏ qua"})
    assert r.json()["error"]["code"] == "CANNOT_WAIVE_CRITICAL"
    # Mọi lỗi tạo được Feedback Case
    fb = qc.post(f"/qc-findings/{f['id']}/feedback").json()
    assert fb["code"].startswith("FB-")
    assert qc.post(f"/qc-findings/{f['id']}/resolve", json={"action": "RESOLVE", "note": "Đã sửa caption, render lại"}).status_code == 200
    r = qc.post(f"/projects/{pid}/qc/final", json={"scores": scores, "notes": "Đạt"})
    expected = "PASS" if sum(v["score"] for v in scores.values()) >= 98 else "FAIL"
    assert r.json()["result"] == expected
    if expected == "PASS":
        assert pm.post(f"/projects/{pid}/approve", json={"decision": "REJECTED"}).status_code == 422  # cần lý do
        assert pm.post(f"/projects/{pid}/approve", json={"decision": "REJECTED", "comment": "Cần đổi nhạc"}).status_code == 200
        assert pm.get(f"/projects/{pid}").json()["status"] == "FINAL_QC"
        qc.post(f"/projects/{pid}/qc/final", json={"scores": scores, "notes": "Đạt lần 2"})
        assert admin.post(f"/projects/{pid}/approve", json={"decision": "APPROVED", "comment": "CEO duyệt"}).status_code == 200
        assert pm.get(f"/projects/{pid}").json()["status"] == "PUBLISH_QUEUED"  # M10 tự chuẩn bị đăng (D29)


def test_render_failure_retry_and_failed_state(login, channels, monkeypatch):
    pm = login("pm")
    pid = _to_scene_qc(pm, channels["CNM"]["id"], "Render lỗi rồi retry")
    from app.modules.rendering import ffmpeg as F

    calls = {"n": 0}
    orig = F.render

    def broken(plan):
        calls["n"] += 1
        raise F.RenderError("FFmpeg lỗi giả lập")

    monkeypatch.setattr(F, "render", broken)
    pm.post(f"/projects/{pid}/render")
    p = pm.get(f"/projects/{pid}").json()
    assert p["status"] == "FAILED" and "FFmpeg lỗi giả lập" in p["last_error"] and calls["n"] == 3  # 1 + 2 retry
    monkeypatch.setattr(F, "render", orig)
    r = pm.post(f"/projects/{pid}/retry", json={"note": "đã sửa"})
    assert r.status_code == 200 and r.json()["resumed"] == "RENDERING", r.text
    p = pm.get(f"/projects/{pid}").json()
    assert p["status"] == "FINAL_QC" and p["retry_count"] == 1
