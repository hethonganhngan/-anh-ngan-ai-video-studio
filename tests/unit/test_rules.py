from app.agents.roles import script_agent as A02
from app.core.permissions import PERMISSIONS, ROLES
from app.core.security import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    mask_secret,
    validate_password_strength,
    verify_password,
)
from app.modules.quality.compliance import has_critical, scan
from app.modules.quality.criteria import CRITERIA
from app.modules.rendering.ffmpeg import ClipIn, RenderPlan, build_command, build_srt
from app.modules.scripts.validation import validate_scenes
from app.providers.video.manual_flow import validate_flow_clip


def test_compliance_detects_bms_under_24_months():
    f = scan("Sữa công thức cho bé sơ sinh, mẹ yên tâm", [])
    assert has_critical(f) and f[0].rule == "BMS_UNDER_24M"


def test_compliance_detects_forbidden_and_medical_and_absolute():
    rules = {x.rule for x in scan("Sản phẩm tốt nhất, chữa biếng ăn hiệu quả 100%", ["tốt nhất"])}
    assert {"FORBIDDEN_TERM", "MEDICAL_CLAIM", "ABSOLUTE_CLAIM"} <= rules


def test_compliance_clean_text():
    assert scan("Mẹ ghé Ánh Ngân để được tư vấn theo nhu cầu của bé nhé", ["tốt nhất"]) == []


def test_scene_rules_two_dialogue_max_and_action_required():
    errors, _ = validate_scenes([{"action": "", "dialogue": [{"text": "a"}, {"text": "b"}, {"text": "c"}], "duration_sec": 8}])
    assert any("tối đa 2" in e for e in errors) and any("thiếu hành động" in e for e in errors)
    errors, warnings = validate_scenes([{"action": "Mẹ bế bé rồi đi ra cửa", "dialogue": [], "duration_sec": 8}])
    assert not errors and any("1 hành động" in w for w in warnings)
    errors, _ = validate_scenes([{"action": "x", "duration_sec": 12}])
    assert any("vượt chuẩn" in e for e in errors)


def test_idea_scoring_is_deterministic_and_penalizes_compliance():
    brief = {"topic": "Chọn sữa", "content_pillars": ["Tư vấn chọn sản phẩm"], "forbidden_terms": ["tốt nhất"],
             "target_audience": "mẹ"}
    good = {"title": "Tư vấn chọn sữa", "hook": "Mẹ ơi, 3 điều cần biết khi chọn sữa?", "summary": "Ánh Ngân tư vấn", "angle": "QA"}
    bad = {**good, "hook": "Sữa tốt nhất cho bé sơ sinh dưới 24 tháng?"}
    s1, s2 = A02.score_idea(good, brief), A02.score_idea(bad, brief)
    assert s1 == A02.score_idea(good, brief)
    assert s1["total"] > s2["total"] and s2["scores"]["compliance"] == 0


def test_mock_script_respects_scene_rules():
    brief = {"topic": "Chọn tã mùa nóng", "duration_sec": 40, "cta": "Ghé Ánh Ngân"}
    idea = {"title": "x", "hook": "Mẹ ơi, tã nào thoáng?"}
    out = A02.mock_script(brief, idea, [], 8)
    assert len(out["scenes"]) == 5
    errors, _ = validate_scenes(out["scenes"])
    assert errors == []
    assert all(len(s["dialogue"]) <= 2 for s in out["scenes"])


def test_flow_clip_validation():
    ok, warn = validate_flow_clip({"width": 1080, "height": 1920, "duration_sec": 8, "has_audio": True})
    assert ok == [] and warn == []
    err, _ = validate_flow_clip({"width": 1920, "height": 1080, "duration_sec": 8, "has_audio": True})
    assert any("Tỉ lệ" in e for e in err)
    err, _ = validate_flow_clip({"width": 360, "height": 640, "duration_sec": 8})
    assert any("Độ phân giải" in e for e in err)
    err, _ = validate_flow_clip({"width": 720, "height": 1280, "duration_sec": 45})
    assert any("Thời lượng" in e for e in err)


def test_srt_timing_and_wrap():
    clips = [ClipIn(path="a", duration=8, has_audio=True, dialogue=[{"text": "Xin chào"}, {"text": "Tạm biệt"}]),
             ClipIn(path="b", duration=8, has_audio=False, trim_start=1, trim_end=5, dialogue=[{"text": "Cảnh hai"}])]
    srt = build_srt(clips)
    assert srt.count("-->") == 3
    assert "00:00:08,150 --> 00:00:11,850" in srt  # cảnh 2 dài 4s sau khi cắt


def test_ffmpeg_command_contains_pipeline():
    plan = RenderPlan(clips=[ClipIn(path="a.mp4", duration=8, has_audio=True), ClipIn(path="b.mp4", duration=8, has_audio=False)],
                      output="o.mp4", srt_path="/tmp/x.srt", logo_path="logo.png")
    cmd = " ".join(build_command(plan))
    for part in ("concat=n=2", "subtitles=", "overlay=", "loudnorm", "anullsrc", "scale=1080:1920", "+faststart"):
        assert part in cmd


def test_password_and_secrets():
    h = hash_password("Abcdefgh12")
    assert verify_password("Abcdefgh12", h) and not verify_password("x", h)
    assert validate_password_strength("short") and not validate_password_strength("Abcdefgh12")
    token = encrypt_secret("sk-ant-1234567890")
    assert token != "sk-ant-1234567890" and decrypt_secret(token) == "sk-ant-1234567890"
    assert mask_secret("sk-ant-1234567890") == "7890"


def test_rbac_catalog_integrity():
    for code, spec in ROLES.items():
        assert set(spec["permissions"]) <= set(PERMISSIONS), code
    assert "project.approve" not in ROLES["QUALITY_REVIEWER"]["permissions"]
    assert "project.approve" not in ROLES["SYSTEM_ADMIN"]["permissions"]
    assert "publish.execute" not in ROLES["CONTENT_CREATOR"]["permissions"]
    assert set(ROLES["VIEWER"]["permissions"]) == {p for p in PERMISSIONS if p.endswith(".view")}
    assert len(ROLES) == 8


def test_qc_has_10_criteria_of_10_points():
    assert len(CRITERIA) == 10 and len({c["key"] for c in CRITERIA}) == 10
    assert {c["method"] for c in CRITERIA} == {"AUTO", "ASSISTED", "MANUAL"}
