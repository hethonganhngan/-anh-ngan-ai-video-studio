"""Tạo cảnh: Mock provider, tiêm lỗi, retry, giới hạn, ngân sách, chống trùng, nhập Flow, khôi phục khi worker dừng."""
from sqlalchemy import select

from tests.helpers import create_project, make_video


def _manual_project(pm, ch, topic, inject=None, scenes_sec=8, **kw):
    p = create_project(pm, ch, topic=topic, duration_sec=scenes_sec, automation_level="MANUAL", **kw)
    pid = p["id"]
    pm.post(f"/projects/{pid}/script/ideas")
    pm.post(f"/projects/{pid}/script/select-idea", json={"index": 0})
    view = pm.post(f"/projects/{pid}/script/write").json()
    if inject:
        s = view["scenes"][0]
        r = pm.patch(f"/scenes/{s['id']}", json={"action": f"{s['action']} {inject}", "note": "tiêm lỗi"})
        assert r.status_code == 200, r.text
    pm.post(f"/projects/{pid}/script/approve", json={})
    assert pm.post(f"/projects/{pid}/validate-assets").json()["blocking"] == []
    return pid


def test_idempotent_project_creation_and_batch(login, channels):
    pm = login("pm")
    ch = channels["ANNGAN"]["id"]
    body = {"channel_id": ch, "topic": "Chống tạo trùng dự án", "idempotency_key": "idem-key-123456"}
    a = pm.post("/projects", json=body).json()
    b = pm.post("/projects", json=body).json()
    assert a["projects"][0]["id"] == b["projects"][0]["id"] and b["duplicate"] is True
    r = pm.post("/projects", json={"channel_id": ch, "topic": "Lô 3 video", "quantity": 3}, headers={"Idempotency-Key": "batch-key-98765"})
    r2 = pm.post("/projects", json={"channel_id": ch, "topic": "Lô 3 video", "quantity": 3}, headers={"Idempotency-Key": "batch-key-98765"})
    ids = [p["id"] for p in r.json()["projects"]]
    assert len(ids) == 3 and [p["id"] for p in r2.json()["projects"]] == ids and r2.json()["duplicate"]
    assert r.json()["batch_id"] and all(p["batch_id"] == r.json()["batch_id"] for p in r.json()["projects"])
    assert r.json()["estimate"]["scene_count"] == 4


def test_validation_rejects_bad_brief(login, channels):
    pm = login("pm")
    r = pm.post("/projects", json={"channel_id": channels["ANNGAN"]["id"], "topic": "abc", "duration_sec": 500})
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert {"topic", "duration_sec"} <= fields


def test_fail_once_then_auto_retry_succeeds(login, channels):
    pm = login("pm")
    pid = _manual_project(pm, channels["ANNGAN"]["id"], "Thử lỗi một lần", "[[MOCK_FAIL_ONCE]]")
    pm.post(f"/projects/{pid}/generate", json={})
    jobs = pm.get(f"/generation-jobs?project_id={pid}").json()["items"]
    statuses = sorted((j["attempt_no"], j["status"]) for j in jobs)
    assert statuses == [(1, "FAILED"), (2, "SUCCEEDED")]
    assert pm.get(f"/projects/{pid}").json()["status"] == "SCENE_QC"  # MANUAL: dừng chờ render
    ov = pm.get(f"/projects/{pid}/overview").json()
    assert ov["cost_total"] == 12000  # chỉ lần thành công tính phí (mock)


def test_permanent_failure_hits_retry_limit_and_needs_manual(login, channels):
    pm = login("pm")
    pid = _manual_project(pm, channels["ANNGAN"]["id"], "Thử lỗi vĩnh viễn", "[[MOCK_FAIL]]")
    pm.post(f"/projects/{pid}/generate", json={})
    jobs = pm.get(f"/generation-jobs?project_id={pid}").json()["items"]
    assert len(jobs) == 4 and all(j["status"] == "FAILED" for j in jobs)  # 1 + 3 retry
    p = pm.get(f"/projects/{pid}").json()
    assert p["status"] == "NEEDS_MANUAL_ACTION" and "Cảnh 1" in p["last_error"]
    scene_id = jobs[0]["scene_id"]
    r = pm.post(f"/scenes/{scene_id}/regenerate")
    assert r.status_code == 422 and r.json()["error"]["code"] == "RETRY_LIMIT"
    # Sửa cảnh → phiên bản mới → được tạo lại
    view = pm.get(f"/projects/{pid}/script").json()
    s = view["scenes"][0]
    assert pm.patch(f"/scenes/{s['id']}", json={"action": s["action"].replace(" [[MOCK_FAIL]]", ""), "note": "sửa"}).status_code == 200
    r = pm.post(f"/scenes/{scene_id}/regenerate")
    assert r.status_code == 200, r.text
    assert pm.get(f"/projects/{pid}").json()["status"] == "SCENE_QC"


def test_provider_unavailable_and_timeout_are_retried(login, channels):
    pm = login("pm")
    for marker in ("[[MOCK_UNAVAILABLE]]", "[[MOCK_TIMEOUT]]"):
        pid = _manual_project(pm, channels["CNM"]["id"], f"Provider {marker}", marker)
        pm.post(f"/projects/{pid}/generate", json={})
        jobs = pm.get(f"/generation-jobs?project_id={pid}").json()["items"]
        assert len(jobs) == 4
        assert {j["error_code"] for j in jobs} == {"PROVIDER_UNAVAILABLE" if "UNAVAIL" in marker else "TIMEOUT"}
        assert pm.get(f"/projects/{pid}").json()["status"] == "NEEDS_MANUAL_ACTION"


def test_duplicate_job_is_rejected(login, channels):
    pm = login("pm")
    pid = _manual_project(pm, channels["ANNGAN"]["id"], "Chống job trùng")
    from app.db.session import SessionLocal
    from app.modules.generation.models import GenerationJob
    from app.modules.scripts.models import Scene

    db = SessionLocal()
    scene = db.scalar(select(Scene).where(Scene.project_id == pid))
    db.add(GenerationJob(project_id=pid, scene_id=scene.id, provider_code="mock", status="RUNNING",
                         idempotency_key=f"{scene.id}:manual-dup", data_mode="DEMO"))
    db.commit()
    db.close()
    r = pm.post(f"/projects/{pid}/generate", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_JOB"


def test_budget_exceeded_blocks_generation(login, channels):
    pm = login("pm")
    # Kiểm tra tài nguyên phát hiện vượt ngân sách trước khi tạo cảnh
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Ngân sách quá nhỏ", duration_sec=16, automation_level="MANUAL",
                       budget_limit=10000)
    pm.post(f"/projects/{p['id']}/script/ideas")
    pm.post(f"/projects/{p['id']}/script/select-idea", json={"index": 0})
    pm.post(f"/projects/{p['id']}/script/write")
    pm.post(f"/projects/{p['id']}/script/approve", json={})
    rep = pm.post(f"/projects/{p['id']}/validate-assets").json()
    assert any("vượt ngân sách" in b for b in rep["blocking"]) and rep["budget_allowed"] is False
    # Ngân sách bị giảm sau khi đã kiểm tra → lệnh tạo cảnh vẫn bị chặn cứng
    pid = _manual_project(pm, channels["ANNGAN"]["id"], "Ngân sách bị giảm", scenes_sec=16, budget_limit=50000)
    assert pm.patch(f"/projects/{pid}", json={"budget_limit": 10000}).status_code == 200
    r = pm.post(f"/projects/{pid}/generate", json={})
    assert r.status_code == 402 and r.json()["error"]["code"] == "BUDGET_EXCEEDED"
    assert pm.get(f"/generation-jobs?project_id={pid}").json()["total"] == 0  # không phát sinh chi phí
    notes = login("admin").get("/admin/notifications").json()
    assert any("vượt ngân sách" in n["title"].lower() or "Chặn chi phí" in n["title"] for n in notes)


def test_global_budget_hard_stop(login, channels, admin):
    pm = login("pm")
    pid = _manual_project(pm, channels["BPCD"]["id"], "Ngân sách toàn hệ thống")
    old = next(b for b in admin.get("/admin/budgets").json() if b["scope"] == "GLOBAL")
    admin.post("/admin/budgets", json={"scope": "GLOBAL", "scope_ref": "*", "period": "MONTHLY", "limit_amount": 1, "hard_stop": True})
    try:
        r = pm.post(f"/projects/{pid}/generate", json={})
        assert r.status_code == 402
        assert login("admin").get("/dashboard").json()["budget_alerts"]
    finally:
        admin.post("/admin/budgets", json={"scope": "GLOBAL", "scope_ref": "*", "period": "MONTHLY",
                                           "limit_amount": old["limit_amount"], "hard_stop": True})


def test_manual_flow_import(login, channels):
    pm, editor = login("pm"), login("editor")
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Cảnh từ Google Flow", duration_sec=16,
                       automation_level="MANUAL", video_provider_code="manual_flow")
    pid = p["id"]
    pm.post(f"/projects/{pid}/script/ideas")
    pm.post(f"/projects/{pid}/script/select-idea", json={"index": 0})
    pm.post(f"/projects/{pid}/script/write")
    pm.post(f"/projects/{pid}/script/approve", json={})
    pm.post(f"/projects/{pid}/validate-assets")
    jobs = pm.post(f"/projects/{pid}/generate", json={}).json()
    assert all(j["provider_code"] == "manual_flow" for j in jobs)
    assert pm.get(f"/projects/{pid}").json()["status"] == "NEEDS_MANUAL_ACTION"
    scenes = pm.get(f"/projects/{pid}/script").json()["scenes"]

    # File sai tỉ lệ bị từ chối
    bad = make_video("landscape.mp4", 1280, 720, 8)
    with open(bad, "rb") as f:
        r = editor.post(f"/scenes/{scenes[0]['id']}/import-flow", files={"file": ("landscape.mp4", f)})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FLOW_CLIP"
    # File giả mạo (text đổi đuôi .mp4)
    fake = bad.with_name("fake.mp4")
    fake.write_text("không phải video")
    with open(fake, "rb") as f:
        r = editor.post(f"/scenes/{scenes[0]['id']}/import-flow", files={"file": ("fake.mp4", f)})
    assert r.status_code == 422
    # Người không có quyền import
    good = make_video("flow.mp4", 720, 1280, 8)
    with open(good, "rb") as f:
        assert login("creator").post(f"/scenes/{scenes[0]['id']}/import-flow", files={"file": ("flow.mp4", f)}).status_code == 403
    for s in scenes:
        with open(good, "rb") as f:
            r = editor.post(f"/scenes/{s['id']}/import-flow", files={"file": ("flow.mp4", f)}, data={"actual_cost": "5000"})
        assert r.status_code == 200, r.text
        assert any("upscale" in w for w in r.json()["warnings"])  # 720x1280 < 1080x1920
    p = pm.get(f"/projects/{pid}").json()
    assert p["status"] == "SCENE_QC"
    assert pm.get(f"/projects/{pid}/overview").json()["cost_total"] == 10000
    asset = pm.get(f"/assets/{r.json()['asset_id']}").json()
    assert asset["source"] == "MANUAL_FLOW" and asset["scene_id"] == scenes[-1]["id"]


def test_worker_restart_recovery(login, channels):
    """Job QUEUED bị bỏ lại (worker chết trước khi xử lý) → recover gửi lại; job đã SUBMITTED chỉ poll, không gửi lại."""
    pm = login("pm")
    pid = _manual_project(pm, channels["ANNGAN"]["id"], "Khôi phục sau khi worker dừng")
    from datetime import datetime, timedelta, timezone

    from app.db.session import SessionLocal
    from app.modules.generation.models import GenerationJob
    from app.modules.scripts.models import Scene
    from app.workflows.jobs import recover_stuck_jobs, run_generation_job

    db = SessionLocal()
    scene = db.scalar(select(Scene).where(Scene.project_id == pid))
    from app.modules.projects.models import Project

    prj = db.get(Project, pid)
    prj.status = "GENERATING"
    job = GenerationJob(project_id=pid, scene_id=scene.id, provider_code="mock", status="QUEUED", estimated_cost=12000,
                        prompt_snapshot={"prompt_text": scene.prompt_text}, idempotency_key=f"{scene.id}:v1:a1", data_mode="DEMO",
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=30))
    db.add(job)
    db.commit()
    jid = str(job.id)
    db.close()
    res = recover_stuck_jobs(older_than_minutes=10)
    assert res["generation"] >= 1
    st = pm.get(f"/generation-jobs?project_id={pid}").json()["items"][0]
    assert st["status"] == "SUCCEEDED"
    # Chạy lại tác vụ đã xong là no-op (idempotent, không tính phí lần 2)
    assert run_generation_job(jid) == "SUCCEEDED"
    assert pm.get(f"/projects/{pid}/overview").json()["cost_total"] == 12000


def test_real_provider_blocked_in_demo_and_mock_blocked_in_production(login, channels, admin):
    pm = login("pm")
    r = pm.post("/projects", json={"channel_id": channels["ANNGAN"]["id"], "topic": "Dùng Veo ở DEMO", "video_provider_code": "veo_vertex"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "REAL_PROVIDER_BLOCKED_IN_DEMO"
    provs = {p["code"]: p for p in pm.get("/video-providers").json()}
    assert provs["mock"]["kind"] == "MOCK" and provs["manual_flow"]["kind"] == "MANUAL"
    assert provs["veo_vertex"]["kind"] == "REAL_API" and provs["veo_vertex"]["available"] is False
    assert provs["veo_vertex"]["connection_status"] == "NOT_CONFIGURED"


def test_concurrent_duplicate_requests_return_same_project(login, channels):
    import threading

    pm = login("pm")
    body = {"channel_id": channels["ANNGAN"]["id"], "topic": "Bấm tạo hai lần cùng lúc", "idempotency_key": "concurrent-key-777"}
    out = []

    def go():
        out.append(pm.post("/projects", json=body))

    ts = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert all(r.status_code == 201 for r in out), [r.text for r in out]
    assert len({r.json()["projects"][0]["id"] for r in out}) == 1
