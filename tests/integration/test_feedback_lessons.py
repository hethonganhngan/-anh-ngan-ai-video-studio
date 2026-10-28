"""Feedback Loop 360° (8 bước, REOPENED, bằng chứng, 4 mắt) và Lessons Learned (duyệt → áp dụng → rollback)."""
from tests.helpers import create_project

EV = [{"type": "URL", "ref": "https://drive.example/qc-report-1", "note": "Biên bản QC"}]


def _users(admin):
    return {u["role"]: u["id"] for u in admin.get("/admin/users/directory").json()}


def _case_to_verify(login, title="Nhân vật đổi trang phục giữa cảnh"):
    qc, pm, admin = login("qc"), login("pm"), login("admin")
    u = _users(admin)
    c = qc.post("/feedback", json={"source": "QC", "category": "CHARACTER", "title": title,
                                   "description": "Cảnh 2 nhân vật mặc áo khác", "evidence_class": "UNKNOWN"}).json()["case"]
    cid = c["id"]
    assert c["status"] == "NEW" and c["code"].startswith("FB-")
    # VALIDATE cần bằng chứng
    r = qc.post(f"/feedback/{cid}/validate", json={"evidence_class": "FACT", "evidence": []})
    assert r.status_code == 422 and r.json()["error"]["code"] == "EVIDENCE_REQUIRED"
    assert qc.post(f"/feedback/{cid}/validate", json={"evidence_class": "FACT", "evidence": EV}).json()["case"]["status"] == "VALIDATED"
    # TRIAGE
    r = qc.post(f"/feedback/{cid}/triage", json={"priority": "P1", "owner_id": u["PRODUCTION_MANAGER"], "kpi_name": "Tỷ lệ cảnh lệch nhân vật (%)",
                                                 "kpi_before": 30, "kpi_target": 5})
    d = r.json()
    assert d["case"]["status"] == "RCA_PENDING" and d["case"]["deadline"]
    # ROOT CAUSE: gợi ý A08 luôn là HYPOTHESIS
    sug = qc.post(f"/feedback/{cid}/rca/suggest").json()
    assert sug["evidence_class"] == "HYPOTHESIS" and len(sug["whys"]) == 5
    assert qc.post(f"/feedback/{cid}/rca", json={"whys": [{"answer": "a"}], "root_cause": "chưa rõ"}).json()["error"]["code"] == "RCA_INCOMPLETE"
    r = qc.post(f"/feedback/{cid}/rca", json={"whys": sug["whys"], "root_cause": "Template prompt thiếu khối Character Lock cố định",
                                              "cause_category": "PROMPT", "evidence_class": "FACT", "confidence_pct": 80})
    assert r.status_code == 200, r.text
    # CAPA
    assert qc.post(f"/feedback/{cid}/capa/approve", json={}).status_code in (403, 422)
    qc.post(f"/feedback/{cid}/capa", json={"action_type": "CORRECTIVE", "description": "Tạo lại cảnh 2 với Character Lock"})
    qc.post(f"/feedback/{cid}/capa", json={"action_type": "PREVENTIVE", "description": "Bổ sung quy tắc vào template A03"})
    r = pm.post(f"/feedback/{cid}/capa/approve", json={"note": "Duyệt"})
    assert r.json()["case"]["status"] == "ACTION_APPROVED", r.text
    # ASSIGN
    d = pm.post(f"/feedback/{cid}/start", json={}).json()
    assert d["case"]["status"] == "IN_PROGRESS"
    assert pm.post(f"/feedback/{cid}/submit-verification", json={}).json()["error"]["code"] == "CAPA_NOT_DONE"
    for a in d["capa"]:
        assert pm.post(f"/feedback/capa/{a['id']}/complete", json={"evidence": []}).status_code == 422
        assert pm.post(f"/feedback/capa/{a['id']}/complete", json={"evidence": [{"type": "ASSET", "ref": "render-v2", "note": "đã làm"}]}).status_code == 200
    assert pm.post(f"/feedback/{cid}/submit-verification", json={}).json()["case"]["status"] == "VERIFY_PENDING"
    return cid


def _full_loop(login):
    qc, pm = login("qc"), login("pm")
    cid = _case_to_verify(login)
    # Không thể kết luận đạt khi KPI chưa đạt mục tiêu
    r = qc.post(f"/feedback/{cid}/verify", json={"method": "Đo lại 20 video", "kpi_after": 12, "passed": True, "evidence": EV})
    assert r.json()["error"]["code"] == "KPI_NOT_MET"
    # Kiểm chứng không đạt → REOPENED
    d = qc.post(f"/feedback/{cid}/verify", json={"method": "Đo lại 20 video", "kpi_after": 12, "passed": False, "evidence": EV,
                                                  "notes": "Vẫn còn lệch"}).json()
    assert d["case"]["status"] == "REOPENED" and d["case"]["reopen_count"] == 1
    # Không đóng được khi chưa xác minh
    assert pm.post(f"/feedback/{cid}/close", json={}).status_code == 409
    pm.post(f"/feedback/{cid}/restart", json={"target": "IN_PROGRESS"})
    d = pm.get(f"/feedback/{cid}").json()
    for a in d["capa"]:
        pm.post(f"/feedback/capa/{a['id']}/complete", json={"evidence": [{"type": "ASSET", "ref": "render-v3"}]})
    pm.post(f"/feedback/{cid}/submit-verification", json={})
    d = qc.post(f"/feedback/{cid}/verify", json={"method": "Đo lại 20 video", "kpi_after": 3, "passed": True, "evidence": EV}).json()
    assert d["case"]["status"] == "VERIFIED" and d["case"]["kpi_after"] == 3
    # STANDARDIZE + tạo bài học
    d = pm.post(f"/feedback/{cid}/standardize", json={
        "note": "Cập nhật template A03 + checklist QC nhân vật", "create_lesson": True,
        "proposed_change": {"template_code": "A03.scene_prompt", "append_negative": "trang phục khác Character Lock",
                            "append_rule": "Luôn mô tả trang phục đúng Character Lock trong mọi cảnh"}}).json()
    assert d["case"]["status"] == "STANDARDIZED" and d["lesson_id"]
    lesson_id = d["lesson_id"]
    d = pm.post(f"/feedback/{cid}/close", json={"note": "Hoàn tất"}).json()
    assert d["case"]["status"] == "CLOSED" and d["case"]["closed_at"]
    steps = [e["step"] for e in d["events"]]
    for s in ["INTAKE", "VALIDATE", "TRIAGE", "ROOT CAUSE", "CAPA", "ASSIGN", "VERIFY", "STANDARDIZE"]:
        assert s in steps, s
    stats = pm.get("/feedback/stats").json()
    assert stats["by_status"].get("CLOSED", 0) >= 1 and stats["capa_verified_rate"] is not None
    return lesson_id


def test_feedback_full_loop_with_reopen(login):
    assert _full_loop(login)


def test_self_approval_of_capa_is_blocked(login):
    pm, admin = login("pm"), login("admin")
    u = _users(admin)
    c = pm.post("/feedback", json={"source": "INTERNAL", "category": "AUDIO", "title": "Âm lượng thấp",
                                   "evidence": EV, "evidence_class": "FACT"}).json()["case"]
    pm.post(f"/feedback/{c['id']}/validate", json={"evidence_class": "FACT", "evidence": []})
    pm.post(f"/feedback/{c['id']}/triage", json={"priority": "P2", "owner_id": u["VIDEO_EDITOR"]})
    pm.post(f"/feedback/{c['id']}/rca", json={"whys": [{"answer": "a"}, {"answer": "b"}, {"answer": "c"}], "root_cause": "Không loudnorm",
                                              "cause_category": "PROCESS", "evidence_class": "HYPOTHESIS", "confidence_pct": 50})
    pm.post(f"/feedback/{c['id']}/capa", json={"action_type": "CORRECTIVE", "description": "Bật loudnorm"})
    r = pm.post(f"/feedback/{c['id']}/capa/approve", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "SELF_APPROVAL"
    assert admin.post(f"/feedback/{c['id']}/capa/approve", json={}).status_code == 200


def test_lesson_approve_apply_rollback_changes_prompt(login, channels):
    lesson_id = _full_loop(login)
    pm, qc = login("pm"), login("qc")
    tpl = next(t for t in pm.get("/prompts/templates").json() if t["code"] == "A03.scene_prompt")
    before_ver = tpl["active_version_no"]
    lesson = pm.get(f"/lessons/{lesson_id}").json()
    assert lesson["status"] == "DRAFT" and lesson["proposed_change"]["template_code"] == "A03.scene_prompt"
    # Chưa duyệt thì không áp dụng
    assert pm.post(f"/lessons/{lesson_id}/apply").json()["error"]["code"] == "LESSON_NOT_APPROVED"
    pm.post(f"/lessons/{lesson_id}/submit")
    assert qc.post(f"/lessons/{lesson_id}/review", json={"approve": True}).status_code == 403
    assert pm.post(f"/lessons/{lesson_id}/review", json={"approve": True, "comment": "OK"}).json()["status"] == "APPROVED"
    applied = pm.post(f"/lessons/{lesson_id}/apply").json()
    assert applied["status"] == "APPLIED" and applied["applied_prompt_version_id"]
    tpl = next(t for t in pm.get("/prompts/templates").json() if t["code"] == "A03.scene_prompt")
    assert tpl["active_version_no"] == before_ver + 1
    # Dự án mới dùng prompt chuẩn mới
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Kiểm tra prompt sau bài học", duration_sec=8)
    pm.post(f"/projects/{p['id']}/script/ideas")
    pm.post(f"/projects/{p['id']}/script/write")
    v = pm.post(f"/projects/{p['id']}/script/approve", json={}).json()
    assert "trang phục khác Character Lock" in v["scenes"][0]["negative_prompt"]
    assert "Luôn mô tả trang phục đúng Character Lock" in v["scenes"][0]["prompt_text"]
    # Prompt đã duyệt bất biến ở DB
    from app.db.session import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        db.execute(text("UPDATE prompt_versions SET content='x' WHERE id=:i"), {"i": applied["applied_prompt_version_id"]})
        db.commit()
        raise AssertionError("phải bị chặn")
    except Exception as e:
        assert "IMMUTABLE_PROMPT" in str(e)
        db.rollback()
    finally:
        db.close()
    # Rollback
    assert pm.post(f"/lessons/{lesson_id}/rollback", json={"reason": ""}).status_code == 422
    rb = pm.post(f"/lessons/{lesson_id}/rollback", json={"reason": "Prompt mới làm cảnh quá dài"}).json()
    assert rb["status"] == "ROLLED_BACK"
    tpl = next(t for t in pm.get("/prompts/templates").json() if t["code"] == "A03.scene_prompt")
    assert tpl["active_version_no"] == before_ver
    # Tìm kiếm
    res = pm.get("/lessons?q=Character Lock&error_category=CHARACTER").json()
    assert any(x["id"] == lesson_id for x in res["items"])
    # DEMO kích hoạt không ảnh hưởng con trỏ PRODUCTION
    assert tpl["production_active_version_id"] != applied["applied_prompt_version_id"]


def test_lesson_manual_and_edit_versions(login):
    creator, pm = login("creator"), login("pm")
    r = creator.post("/lessons", json={"lesson_type": "EFFECTIVE_PROMPT", "title": "Hook dạng câu hỏi hiệu quả",
                                       "lesson": "Hook câu hỏi 3 giây tăng giữ chân", "error_category": "SCRIPT", "provider_code": "mock"})
    x = r.json()
    assert x["version_no"] == 1
    x = creator.patch(f"/lessons/{x['id']}", json={"lesson": "Hook câu hỏi ≤ 12 từ tăng giữ chân"}).json()
    assert x["version_no"] == 2 and len(x["history"]) == 1
    creator.post(f"/lessons/{x['id']}/submit")
    assert pm.post(f"/lessons/{x['id']}/review", json={"approve": False}).status_code == 422
    assert pm.post(f"/lessons/{x['id']}/review", json={"approve": False, "comment": "Thiếu số liệu"}).json()["status"] == "REJECTED"


def test_critical_qc_finding_auto_creates_feedback(login, channels):
    """A08 tự tạo Feedback Case P0 khi render có vi phạm tuân thủ CRITICAL."""
    pm = login("pm")
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Video thử vi phạm tuân thủ", duration_sec=8)
    pid = p["id"]
    pm.post(f"/projects/{pid}/script/ideas")
    view = pm.post(f"/projects/{pid}/script/write").json()
    cur = view["current"]
    cur_scenes = [{k: s[k] for k in ("title", "scene_type", "action", "dialogue", "setting", "camera", "lighting", "sound", "duration_sec")}
                  for s in view["scenes"]]
    cur_scenes[0]["dialogue"] = [{"speaker": "Chị Ngân", "text": "Sản phẩm giúp chữa biếng ăn cho bé"}]
    r = pm.put(f"/projects/{pid}/script", json={"title": cur["title"], "hook": cur["hook"], "body": cur["body"], "cta": cur["cta"],
                                                 "scenes": cur_scenes, "note": "thêm câu vi phạm"})
    assert any(c["severity"] == "CRITICAL" for c in r.json()["check"]["compliance"])
    r = pm.post(f"/projects/{pid}/script/approve", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "COMPLIANCE_CRITICAL"
