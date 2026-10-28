"""M14/M15: Agent scope & logs, provider secret, audit append-only, chế độ DEMO/PRODUCTION tách dữ liệu, backup/restore."""
import pytest
from sqlalchemy import text

from tests.helpers import create_project


def test_agents_registry_and_execution_logs(login, channels):
    pm, admin = login("pm"), login("admin")
    agents = admin.get("/agents").json()
    assert [a["code"] for a in agents] == [f"A{i:02d}" for i in range(1, 11)]
    assert all(a["allowed_actions"] for a in agents)
    assert not any("approve" in act or "publish" in act for a in agents for act in a["allowed_actions"])
    p = create_project(pm, channels["ANNGAN"]["id"], topic="Ghi log agent", duration_sec=8)
    pm.post(f"/projects/{p['id']}/script/ideas")
    ex = admin.get("/agents/executions?agent_code=A02").json()["items"][0]
    assert ex["status"] == "SUCCEEDED" and ex["model"] == "mock-deterministic-v1" and ex["provider_code"] == "mock-llm"
    assert ex["input_tokens"] > 0 and ex["output_tokens"] > 0 and ex["latency_ms"] >= 0 and ex["is_simulated"]
    assert ex["prompt_version_label"] == "A02.script"
    a02 = admin.get("/agents/A02").json()
    assert a02["stats"]["runs"] >= 1 and a02["stats"]["tokens"] > 0


def test_agent_scope_violation_is_blocked_and_audited(login):
    from app.agents.runner import AgentScopeError, run_agent
    from app.core.context import SYSTEM_ACTOR, Ctx
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        ctx = Ctx(db=db, actor=SYSTEM_ACTOR, mode="DEMO")
        with pytest.raises(AgentScopeError):
            run_agent(ctx, "A07", "project.approve", lambda llm, a: ({}, None))
        with pytest.raises(AgentScopeError):
            run_agent(ctx, "A10", "publish.execute", lambda llm, a: ({}, None))
    finally:
        db.close()
    logs = login("admin").get("/admin/audit-logs?action=agent.scope_violation").json()
    assert logs["total"] >= 2
    # Agent ctx không có quyền nghiệp vụ của người dùng
    from app.core.context import Ctx as C2

    c = C2(db=None, actor=SYSTEM_ACTOR, mode="DEMO").as_agent("A07", ["qc.final_check"])
    assert not c.actor.has("project.approve")


def test_agent_disable_and_limits(login, channels):
    admin, pm = login("admin"), login("pm")
    assert login("pm").patch("/agents/A02", json={"is_enabled": False}).status_code == 403
    admin.patch("/agents/A02", json={"is_enabled": False})
    try:
        p = create_project(pm, channels["ANNGAN"]["id"], topic="Agent bị tắt", duration_sec=8)
        r = pm.post(f"/projects/{p['id']}/script/ideas")
        assert r.status_code == 409 and r.json()["error"]["code"] == "AGENT_DISABLED"
    finally:
        admin.patch("/agents/A02", json={"is_enabled": True})
    r = admin.patch("/agents/A07", json={"provider_code": "anthropic"})
    assert r.status_code == 422  # rule-engine không dùng LLM
    r = admin.patch("/agents/A02", json={"provider_code": "openai-x"})
    assert r.status_code == 422
    old = admin.get("/agents/A02").json()["max_runs_per_day"]
    admin.patch("/agents/A02", json={"max_runs_per_day": 1})
    try:
        p = create_project(pm, channels["ANNGAN"]["id"], topic="Giới hạn lượt chạy agent", duration_sec=8)
        r = pm.post(f"/projects/{p['id']}/script/ideas")
        assert r.status_code == 429 and r.json()["error"]["code"] == "AGENT_LIMIT_EXCEEDED"
    finally:
        admin.patch("/agents/A02", json={"max_runs_per_day": old})


def test_provider_secret_is_masked_and_encrypted(login):
    admin = login("admin")
    provs = {p["provider_code"]: p for p in admin.get("/admin/providers").json()}
    pid = provs["anthropic"]["id"]
    r = admin.patch(f"/admin/providers/{pid}", json={"config": {"api_key": "x"}})
    assert r.status_code == 422
    r = admin.patch(f"/admin/providers/{pid}", json={"api_key": "sk-ant-api03-SECRETVALUE-9876"}).json()
    assert r["secret_last4"] == "9876" and "SECRETVALUE" not in str(r)
    assert r["connection_status"] == "CONFIGURED_UNVERIFIED"
    assert "SECRETVALUE" not in admin.get("/admin/providers").text
    from app.db.session import SessionLocal

    db = SessionLocal()
    raw = db.execute(text("select secret_encrypted from provider_accounts where provider_code='anthropic'")).scalar()
    db.close()
    assert raw and "SECRETVALUE" not in raw
    # DEMO: không gọi API LLM thật để test
    assert admin.post(f"/admin/providers/{pid}/test").status_code == 422
    logs = admin.get("/admin/audit-logs?action=provider.update").json()["items"]
    assert all("SECRETVALUE" not in str(x) for x in logs)


def test_audit_log_is_append_only(login):
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        with pytest.raises(Exception) as ei:
            db.execute(text("DELETE FROM audit_logs"))
            db.commit()
        assert "AUDIT_APPEND_ONLY" in str(ei.value)
    finally:
        db.rollback()
        db.close()


def test_mode_switch_separates_data(login, channels):
    admin, pm = login("admin"), login("pm")
    demo_project = create_project(pm, channels["ANNGAN"]["id"], topic="Dự án DEMO tách biệt", duration_sec=8)
    assert admin.post("/admin/mode", json={"mode": "PRODUCTION", "confirm_text": "production"}).status_code == 422
    assert login("sysadmin").post("/admin/mode", json={"mode": "PRODUCTION", "confirm_text": "PRODUCTION"}).status_code == 200
    try:
        me = pm.get("/auth/me").json()
        assert me["mode"] == "PRODUCTION"
        ids = [p["id"] for p in pm.get("/projects").json()["items"]]
        assert demo_project["id"] not in ids
        assert pm.get(f"/projects/{demo_project['id']}").status_code == 404
        # PRODUCTION không cho Mock provider; LLM chưa kết nối → agent báo rõ, có thể viết thủ công
        r = pm.post("/projects", json={"channel_id": channels["ANNGAN"]["id"], "topic": "Dự án thật", "video_provider_code": "mock"})
        assert r.json()["error"]["code"] == "MOCK_NOT_ALLOWED_IN_PRODUCTION"
        p = pm.post("/projects", json={"channel_id": channels["ANNGAN"]["id"], "topic": "Dự án thật dùng Flow",
                                       "video_provider_code": "manual_flow", "duration_sec": 8}).json()["projects"][0]
        assert p["data_mode"] == "PRODUCTION"
        r = pm.post(f"/projects/{p['id']}/script/ideas")
        assert r.status_code == 409 and r.json()["error"]["code"] == "LLM_NOT_CONNECTED"
        manual = {"title": "Thủ công", "hook": "Mẹ ơi, tã nào thoáng mát?", "body": "Kịch bản viết tay", "cta": "Ghé Ánh Ngân",
                  "scenes": [{"title": "Cảnh 1", "action": "Tư vấn viên giới thiệu", "dialogue": [{"speaker": "Ngân", "text": "Chào mẹ"}],
                              "duration_sec": 8}], "note": "viết tay"}
        r = pm.put(f"/projects/{p['id']}/script", json=manual)
        assert r.status_code == 200 and r.json()["project"]["status"] == "SCRIPT_REVIEW"
        assert pm.get("/dashboard").json()["mode"] == "PRODUCTION"
    finally:
        admin.post("/admin/mode", json={"mode": "DEMO", "confirm_text": "DEMO"})
    assert pm.get(f"/projects/{demo_project['id']}").status_code == 200


def test_settings_and_budget_management(login):
    admin, pm = login("admin"), login("pm")
    s = admin.get("/admin/settings").json()
    assert s["qc.policy"]["min_total"] == 98
    assert admin.put("/admin/settings/qc.policy", json={"value": {"min_total": 50}}).status_code == 422
    assert admin.put("/admin/settings/system.mode", json={"value": {"value": "PRODUCTION"}}).status_code == 422
    r = admin.post("/admin/budgets", json={"scope": "PROVIDER", "scope_ref": "mock", "period": "DAILY", "limit_amount": 999999999})
    assert r.status_code == 201
    assert any(b["scope"] == "PROVIDER" for b in pm.get("/admin/budgets").json())
    assert admin.delete(f"/admin/budgets/{r.json()['id']}").status_code == 200
    costs = pm.get("/admin/costs").json()
    assert "by_category" in costs and costs["simulated_total"] == costs["total"]
    h = admin.get("/admin/health").json()
    assert h["checks"]["database"]["ok"] and h["checks"]["ffmpeg"]["ok"] and h["checks"]["storage"]["ok"]


def test_backup_and_restore_round_trip(login, channels):
    admin, pm = login("admin"), login("pm")
    keep = create_project(pm, channels["ANNGAN"]["id"], topic="Có trước khi sao lưu", duration_sec=8)
    b = admin.post("/admin/backups", json={"note": "test"}).json()
    assert b["file_name"].endswith(".dump") and b["size_bytes"] > 0 and len(b["checksum"]) == 64
    lost = create_project(pm, channels["ANNGAN"]["id"], topic="Tạo sau khi sao lưu", duration_sec=8)
    assert login("sysadmin").post("/admin/backups/restore", json={"file_name": b["file_name"],
                                                                   "confirm_text": f"RESTORE {b['file_name']}"}).status_code == 422
    assert admin.post("/admin/backups/restore", json={"file_name": "../../etc/passwd", "confirm_text": "RESTORE ../../etc/passwd"}).status_code == 422
    assert admin.post("/admin/backups/restore", json={"file_name": b["file_name"], "confirm_text": "yes"}).status_code == 422
    r = admin.post("/admin/backups/restore", json={"file_name": b["file_name"], "confirm_text": f"RESTORE {b['file_name']}"})
    assert r.status_code == 200, r.text
    assert pm.get(f"/projects/{keep['id']}").status_code == 200
    assert pm.get(f"/projects/{lost['id']}").status_code == 404
    logs = admin.get("/admin/audit-logs?action=backup.restore").json()
    assert logs["total"] >= 1


def test_clear_provider_api_key(login):
    admin = login("admin")
    pid = next(p for p in admin.get("/admin/providers").json() if p["provider_code"] == "youtube_data")["id"]
    assert admin.patch(f"/admin/providers/{pid}", json={"api_key": "yt-key-123456789"}).json()["secret_last4"] == "6789"
    r = admin.patch(f"/admin/providers/{pid}", json={"clear_api_key": True}).json()
    assert r["secret_last4"] is None and r["connection_status"] == "NOT_CONFIGURED" and r["is_enabled"] is False


def test_worker_registers_all_tasks():
    import app.celery_app as worker
    from app.workflows.tasks_registry import TASK_NAMES

    for name in TASK_NAMES:
        assert name in worker.celery.tasks, name
    assert "recover-stuck-jobs" in worker.celery.conf.beat_schedule
