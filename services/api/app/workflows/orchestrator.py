"""A01 AI Director — điều phối workflow.

Nguyên tắc: Agent chỉ chạy các bước tự động; dừng ở mọi cổng cần con người (duyệt kịch bản, QC tổng thể,
phê duyệt phát hành, xuất bản). MANUAL: mỗi lần advance chạy 1 bước; ASSISTED/AUTO: chạy liên tiếp tới cổng kế.
AUTO còn tự duyệt kịch bản sạch và tự lồng giọng M04 trước khi dựng → chạy một mạch tới FINAL_QC (video hoàn chỉnh)."""
from app.agents.runner import run_agent
from app.core.context import Ctx
from app.core.errors import AppError, InvalidTransition, ValidationFailed
from app.modules.projects.service import get_project, lock_project
from app.workflows import state_machine as sm
from sqlalchemy import select

HUMAN_GATES = {
    "SCRIPT_REVIEW": "Chờ duyệt kịch bản (M03)",
    "FINAL_QC": "Chờ Quality Reviewer chấm 10 tiêu chí (M07)",
    "APPROVAL_PENDING": "Chờ người có quyền phê duyệt (M07)",
    "APPROVED": "Chờ lên lịch phát hành (M10)",
    "PUBLISH_QUEUED": "Chờ xuất bản (M10)",
    "NEEDS_MANUAL_ACTION": "Cần thao tác thủ công",
    "FAILED": "Lỗi — cần Retry hoặc Huỷ",
    "CANCELLED": "Đã huỷ",
    "PUBLISHED": "Đã xuất bản — nhập số liệu analytics (M10)",
    "ANALYTICS_COLLECTION": "Đang thu thập số liệu",
    "FEEDBACK_REVIEW": "Rà soát phản hồi",
    "RENDERING": "Đang render (worker)",
    "GENERATING": "Đang tạo cảnh (worker)",
}


def _step(ctx: Ctx, p) -> str | None:
    """Thực hiện 1 bước tự động. Trả về mô tả, hoặc None nếu đang ở cổng con người/đang chờ worker."""
    from app.modules.generation import service as gen
    from app.modules.scripts import service as scripts
    from app.modules.scripts.models import Script

    st = p.status
    if st == "CREATED":
        scripts.generate_ideas(ctx, p.id)
        return "A02 tạo & chấm 3 ý tưởng"
    if st == "SCRIPT_GENERATING":
        script = ctx.db.scalar(select(Script).where(Script.project_id == p.id))
        if not script or not script.ideas:
            scripts.generate_ideas(ctx, p.id)
            return "A02 tạo & chấm 3 ý tưởng"
        if script.selected_idea_index is None:
            return None  # MANUAL: chờ người chọn ý tưởng
        scripts.write_script(ctx, p.id)
        return "A02 viết kịch bản & storyboard"
    if st == "SCRIPT_REVIEW" and p.automation_level == "AUTO":
        # Chính sách AUTO (CEO chốt 2026-10-29, D19): duyệt thay người bấm khi kịch bản sạch. approve_script vẫn chặn
        # lỗi storyboard và vi phạm tuân thủ CRITICAL (vd sữa cho trẻ < 24 tháng) → dừng ở cổng chờ người duyệt.
        scripts.approve_script(ctx, p.id, comment="Tự duyệt (AUTO): không có lỗi hay vi phạm tuân thủ nghiêm trọng")
        return "Tự duyệt kịch bản (AUTO)"
    if st == "STORYBOARD_READY":
        gen.validate_assets(ctx, p.id)
        return "A04 kiểm tra tài nguyên"
    if st == "GENERATION_QUEUED":
        gen.queue_generation(ctx, p.id)
        return "A05 gửi tác vụ tạo cảnh"
    if st == "SCENE_QC":
        from app.modules.rendering.service import start_render
        from app.modules.scripts.models import Scene

        scenes = ctx.db.scalars(select(Scene).where(Scene.project_id == p.id)).all()
        if all(s.status == "QC_PASSED" for s in scenes):
            start_render(ctx, p, None)
            return "A06 bắt đầu render"
        return None
    return None


def advance_project(ctx: Ctx, project_id) -> dict:
    p = lock_project(ctx, project_id)
    steps: list[str] = []

    def work(_llm, actx):
        max_steps = 1 if p.automation_level == "MANUAL" else 8
        for _ in range(max_steps):
            ctx.db.flush()  # KHÔNG refresh: sẽ huỷ thay đổi chưa flush của chính vòng trước
            try:
                done = _step(ctx, p)
            except AppError as e:
                steps.append(f"Dừng: {e.message}")
                break
            if not done:
                break
            steps.append(done)
        return {"result": steps, "count": len(steps)}, None

    run_agent(ctx, "A01", "project.orchestrate", work, project=p, input_ref={"project": p.code, "status": p.status})
    ctx.db.flush()
    return {"steps": steps, "status": p.status, "waiting_for": HUMAN_GATES.get(p.status)}


def retry_project(ctx: Ctx, project_id, note: str = "") -> dict:
    """FAILED → RETRY_PENDING → chạy lại đúng bước đã lỗi (resume_status)."""
    from app.modules.generation import service as gen
    from app.modules.rendering.service import start_render
    from app.modules.scripts import service as scripts

    p = lock_project(ctx, project_id)
    if p.status == "FAILED":
        sm.transition(ctx, p, "RETRY_PENDING", note=note or "Yêu cầu chạy lại")
    if p.status != "RETRY_PENDING":
        raise InvalidTransition(f"Chỉ retry dự án FAILED/RETRY_PENDING (hiện tại {p.status})")
    resume = p.resume_status or "GENERATING"

    def work(_llm, _actx):
        if resume == "SCRIPT_GENERATING":
            scripts.generate_ideas(ctx, p.id)
        elif resume == "GENERATING":
            gen.queue_generation(ctx, p.id)
        elif resume == "RENDERING":
            start_render(ctx, p, None)
        elif resume == "PUBLISH_QUEUED":
            sm.transition(ctx, p, "PUBLISH_QUEUED", note="Chạy lại xuất bản")
        else:
            raise ValidationFailed(f"Không hỗ trợ retry bước {resume}")
        return {"result": resume}, None

    run_agent(ctx, "A01", "workflow.retry", work, project=p, input_ref={"resume": resume})
    return {"status": p.status, "resumed": resume, "retry_count": p.retry_count}


def resolve_manual_action(ctx: Ctx, project_id, note: str) -> dict:
    """Sau khi xử lý thủ công (khoá nhân vật, nạp ngân sách, nhập Flow…) → kiểm tra lại từ bước phù hợp."""
    from app.modules.generation import service as gen
    from app.modules.generation.models import GenerationJob
    from app.modules.scripts.models import Scene

    p = get_project(ctx, project_id)
    if p.status != "NEEDS_MANUAL_ACTION":
        raise InvalidTransition("Dự án không ở trạng thái cần thao tác thủ công")
    has_jobs = ctx.db.scalar(select(GenerationJob.id).where(GenerationJob.project_id == p.id).limit(1))
    if not has_jobs:
        report = gen.validate_assets(ctx, p.id)
        return {"status": p.status, "report": report}
    scenes = ctx.db.scalars(select(Scene).where(Scene.project_id == p.id)).all()
    pending = [s for s in scenes if s.status not in ("GENERATED", "QC_PASSED")]
    lp = lock_project(ctx, project_id)
    sm.transition(ctx, lp, "GENERATING", note=note or "Tiếp tục sau thao tác thủ công")
    if pending:
        manual = [s for s in pending if s.status == "NEEDS_MANUAL"]
        regen = [s for s in pending if s.status != "NEEDS_MANUAL"]
        if regen:
            gen.queue_generation(ctx, p.id, [s.id for s in regen])
        if manual and not regen:
            sm.transition(ctx, lp, "NEEDS_MANUAL_ACTION", note="Vẫn còn cảnh chờ nhập từ Flow")
    else:
        from app.workflows.jobs import _after_scene_change

        _after_scene_change(ctx, lp)
    return {"status": lp.status}


def project_overview(ctx: Ctx, project_id) -> dict:
    from app.modules.administration.service import spent
    from app.modules.generation.models import GenerationJob
    from app.modules.projects.schemas import ProjectOut, WorkflowEventOut
    from app.modules.projects.service import events
    from app.modules.rendering.models import Render, RenderJob
    from app.modules.scripts.models import Scene

    p = get_project(ctx, project_id)
    scenes = ctx.db.scalars(select(Scene).where(Scene.project_id == p.id).order_by(Scene.order_index)).all()
    jobs = ctx.db.scalars(select(GenerationJob).where(GenerationJob.project_id == p.id)).all()
    renders = ctx.db.scalars(select(Render).where(Render.project_id == p.id).order_by(Render.version_no.desc())).all()
    rjobs = ctx.db.scalars(select(RenderJob).where(RenderJob.project_id == p.id).order_by(RenderJob.created_at.desc())).all()
    step = sm.STEPS.get(p.status)
    return {
        "project": ProjectOut.model_validate(p).model_dump(mode="json"),
        "step": step.__dict__ if step else None,
        "allowed_transitions": sorted(sm.TRANSITIONS.get(p.status, set())),
        "waiting_for": HUMAN_GATES.get(p.status),
        "scenes": [{"id": str(s.id), "order_index": s.order_index, "title": s.title, "status": s.status,
                    "selected_asset_id": str(s.selected_asset_id) if s.selected_asset_id else None} for s in scenes],
        "jobs_by_status": {st: sum(1 for j in jobs if j.status == st) for st in {j.status for j in jobs}},
        "renders": [{"id": str(r.id), "version_no": r.version_no, "video_asset_id": str(r.video_asset_id),
                     "thumbnail_asset_id": str(r.thumbnail_asset_id) if r.thumbnail_asset_id else None,
                     "status": r.status, "duration_sec": r.duration_sec} for r in renders],
        "render_jobs": [{"id": str(j.id), "status": j.status, "attempt_no": j.attempt_no, "error": j.error_message,
                         "log": j.log} for j in rjobs[:5]],
        "cost_total": float(spent(ctx.db, ctx.mode, project_id=p.id)),
        "events": [WorkflowEventOut.model_validate(e).model_dump(mode="json") for e in events(ctx, p.id)],
    }
