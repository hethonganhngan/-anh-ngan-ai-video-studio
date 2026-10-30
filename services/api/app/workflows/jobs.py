"""Thân tác vụ nền (chạy trong Celery worker hoặc eager). Mỗi tác vụ idempotent:
- khoá bản ghi bằng FOR UPDATE SKIP LOCKED (2 worker không xử lý cùng job),
- trạng thái đã kết thúc → bỏ qua, đã SUBMITTED → chỉ poll (không gửi lại, không tính phí 2 lần)."""
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.context import Actor, Ctx
from app.core.errors import AppError, BudgetExceeded
from app.db.session import SessionLocal
from app.workflows.dispatch import defer
from sqlalchemy import func, select

log = logging.getLogger("anngan.jobs")
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "BLOCKED_BUDGET"}


def _now():
    return datetime.now(timezone.utc)


def _agent_ctx(db, mode: str, code: str) -> Ctx:
    from app.agents.models import AgentConfig

    cfg = db.get(AgentConfig, code)
    return Ctx(db=db, actor=Actor(type="AGENT", id=code, label=cfg.name if cfg else code,
                                  permissions=set(cfg.allowed_actions if cfg else [])), mode=mode)


def _log(job, msg: str) -> None:
    job.log = [*(job.log or []), {"at": _now().isoformat(), "msg": msg[:500]}]


# ====================== GENERATION ======================
def run_generation_job(job_id: str) -> str:
    from app.modules.generation.models import GenerationJob

    db = SessionLocal()
    try:
        job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id).with_for_update(skip_locked=True))
        if job is None or job.status in TERMINAL or job.status == "NEEDS_MANUAL_ACTION":
            return job.status if job else "MISSING"
        result = _process_generation(db, job)
        db.commit()
        return result
    finally:
        db.close()


def poll_generation_job(job_id: str) -> str:
    return run_generation_job(job_id)


REF_ORDER = ("FRONT", "THREE_QUARTER", "OUTFIT", "FULL_BODY", "EXPRESSION")


def _reference_images(db, project, scene) -> list[str]:
    """Ảnh tham chiếu từ Character Lock đã duyệt (M04) của nhân vật trong cảnh → provider giữ mặt/trang phục đồng nhất.
    Chỉ khi cảnh có đúng 1 nhân vật (ảnh 'asset' của Veo mô tả 1 chủ thể); tối đa 3 ảnh, ưu tiên mặt chính diện."""
    from app.media.models import Asset
    from app.media.storage import get_storage
    from app.modules.characters.models import Character, CharacterLock

    ids = scene.character_ids or project.character_ids or []
    if len(ids) != 1:
        return []
    c = db.get(Character, ids[0])
    lock = db.get(CharacterLock, c.active_lock_id) if c and c.active_lock_id else None
    if lock is None:
        return []
    refs = (lock.lock_data or {}).get("references") or {}
    paths = []
    for ref_type in sorted(refs, key=lambda t: REF_ORDER.index(t) if t in REF_ORDER else len(REF_ORDER)):
        asset = db.get(Asset, (refs[ref_type] or {}).get("asset_id"))
        path = get_storage().local_path(asset.storage_key) if asset else None
        if path and os.path.exists(path):
            paths.append(path)
    return paths[:3]


def _process_generation(db, job) -> str:
    from app.agents.runner import run_agent
    from app.modules.administration import service as admin
    from app.modules.projects.models import Project
    from app.modules.scripts.models import Scene
    from app.providers.video.base import GenerationSpec, ProviderError
    from app.providers.video.registry import get_video_provider

    project = db.get(Project, job.project_id)
    scene = db.get(Scene, job.scene_id)
    ctx = _agent_ctx(db, job.data_mode, "A05")
    if project.status == "CANCELLED":
        job.status = "CANCELLED"
        return job.status
    try:
        provider = get_video_provider(db, job.provider_code, job.data_mode)
    except AppError as e:
        return _generation_failed(ctx, job, scene, project, "PROVIDER_UNAVAILABLE", e.message, retryable=False)

    if job.status in ("QUEUED", "RETRY_PENDING"):
        try:
            admin.check_budget(ctx, estimated=Decimal(job.estimated_cost), project=project, provider_code=job.provider_code)
        except BudgetExceeded as e:
            job.status = "BLOCKED_BUDGET"
            job.error_code = "BUDGET_EXCEEDED"
            job.error_message = e.message
            _log(job, f"Chặn do ngân sách: {e.message}")
            scene.status = "NEEDS_MANUAL"
            _after_scene_change(ctx, project)
            return job.status
        spec = GenerationSpec(job_ref=str(job.id), prompt_text=job.prompt_snapshot.get("prompt_text", ""),
                              negative_prompt=job.prompt_snapshot.get("negative_prompt", ""),
                              duration_sec=scene.duration_sec, aspect_ratio=project.aspect_ratio,
                              scene_title=scene.title, dialogue=scene.dialogue, attempt_no=job.attempt_no,
                              reference_image_paths=_reference_images(db, project, scene))
        issues = provider.validate_capabilities(spec)
        if issues:
            return _generation_failed(ctx, job, scene, project, "CAPABILITY", "; ".join(issues), retryable=False)

        def submit(_llm, _actx):
            return {"result": provider.submit_generation(spec)}, None

        try:
            run = run_agent(ctx, "A05", "generation.submit", submit, project=project,
                            input_ref={"job": str(job.id), "scene": scene.order_index, "provider": provider.code,
                                       "attempt": job.attempt_no})
        except ProviderError as e:
            return _generation_failed(ctx, job, scene, project, e.code, str(e), retryable=e.retryable)
        except AppError as e:
            return _generation_failed(ctx, job, scene, project, e.code, e.message, retryable=False)
        job.provider_job_id = run.output["result"]
        job.status = "SUBMITTED"
        job.started_at = _now()
        _log(job, f"Đã gửi {provider.name}: {job.provider_job_id}")
        db.flush()
        db.commit()  # mốc an toàn: worker chết sau điểm này sẽ chỉ poll, không gửi lại
        job = db.scalar(select(type(job)).where(type(job).id == job.id).with_for_update())

    try:
        st = provider.get_status(job.provider_job_id)
    except ProviderError as e:
        if e.retryable:
            _log(job, f"Poll lỗi tạm thời: {e}")
            from app.workflows.celery_client import enqueue_later

            enqueue_later("anngan.generation.poll_job", 20, str(job.id))
            return job.status
        return _generation_failed(ctx, job, scene, project, e.code, str(e), retryable=False)
    if st.state == "SUCCEEDED":
        return _generation_succeeded(ctx, job, scene, project, provider)
    if st.state == "NEEDS_MANUAL_ACTION":
        job.status = "NEEDS_MANUAL_ACTION"
        scene.status = "NEEDS_MANUAL"
        _log(job, st.error_message or "Chờ thao tác thủ công")
        _after_scene_change(ctx, project)
        return job.status
    if st.state in ("FAILED", "CANCELLED"):
        return _generation_failed(ctx, job, scene, project, st.error_code or "GENERATION_FAILED",
                                  st.error_message or "Nhà cung cấp báo lỗi", retryable=st.state == "FAILED")
    job.status = "RUNNING"
    from app.workflows.celery_client import enqueue_later

    enqueue_later("anngan.generation.poll_job", 15, str(job.id))
    return job.status


def _generation_succeeded(ctx: Ctx, job, scene, project, provider) -> str:
    from app.media.service import ingest_file
    from app.media.storage import safe_remove
    from app.modules.administration import service as admin

    path = provider.get_result(job.provider_job_id)
    asset = ingest_file(ctx, path, f"{project.code}_S{scene.order_index + 1:02d}_v{scene.current_version_no}_a{job.attempt_no}.mp4",
                        asset_type="VIDEO", source="MOCK_PROVIDER" if provider.kind == "MOCK" else "API_PROVIDER",
                        usage_rights="AI_GENERATED", tags=["scene", provider.code, project.code],
                        channel_id=project.channel_id, project_id=project.id, scene_id=scene.id,
                        extra_info={"provider": provider.code, "generation_job_id": str(job.id),
                                    "prompt_version_id": job.prompt_snapshot.get("prompt_version_id")},
                        rights_note="DEMO — tạo bởi Mock Provider" if provider.kind == "MOCK" else "")
    if provider.kind == "MOCK":
        safe_remove(path)
    cost = Decimal(job.estimated_cost)
    job.actual_cost = cost
    if cost > 0:
        admin.record_cost(ctx.db, ctx.mode, category="VIDEO_GEN", provider_code=provider.code, amount=cost,
                          quantity=Decimal(scene.duration_sec), unit="SECOND", project=project, scene_id=scene.id,
                          generation_job_id=job.id, is_simulated=not provider.is_real,
                          description=f"{project.code} cảnh {scene.order_index + 1} lần {job.attempt_no}")
    job.status = "SUCCEEDED"
    job.result_asset_id = asset.id
    job.finished_at = _now()
    _log(job, f"Hoàn tất, asset {asset.id}")
    scene.selected_asset_id = asset.id
    scene.status = "GENERATED"
    _after_scene_change(ctx, project)
    return job.status


def _generation_failed(ctx: Ctx, job, scene, project, code: str, message: str, retryable: bool) -> str:
    from app.modules.generation.models import GenerationJob

    job.error_code = code
    job.error_message = message[:2000]
    job.finished_at = _now()
    _log(job, f"Lỗi {code}: {message}")
    if retryable and job.attempt_no <= job.max_retries:
        job.status = "FAILED"
        nxt = GenerationJob(project_id=job.project_id, scene_id=job.scene_id, scene_version_no=job.scene_version_no,
                            provider_code=job.provider_code, status="QUEUED", attempt_no=job.attempt_no + 1,
                            max_retries=job.max_retries, prompt_snapshot=job.prompt_snapshot,
                            estimated_cost=job.estimated_cost, requested_by=job.requested_by, data_mode=job.data_mode,
                            idempotency_key=f"{job.idempotency_key.rsplit(':a', 1)[0]}:a{job.attempt_no + 1}")
        ctx.db.add(nxt)
        ctx.db.flush()
        _log(nxt, f"Tự động thử lại lần {nxt.attempt_no} sau lỗi {code}")
        scene.status = "GENERATING"
        defer(ctx.db, "anngan.generation.run_job", str(nxt.id))
        return "RETRY_SCHEDULED"
    job.status = "FAILED"
    scene.status = "GENERATION_FAILED"
    _after_scene_change(ctx, project)
    return job.status


def _auto_voiceover(ctx: Ctx, project) -> None:
    """AUTO: lồng thoại bằng giọng Voice Profile (M04) của dự án trước khi dựng. Lỗi không chặn dựng
    (video vẫn có phụ đề) — ghi vào last_error để người dùng biết và tạo lại giọng ở M06."""
    from app.modules.administration.models import ProviderAccount
    from app.modules.rendering.voiceover import generate_voiceover

    # provider có thể tự sinh tiếng nói (vd. Flow) → cấu hình hạ tiếng gốc về 0 để không chồng 2 giọng
    acc = ctx.db.scalar(select(ProviderAccount).where(ProviderAccount.provider_code == project.video_provider_code))
    volume = float((acc.config or {}).get("voiceover_scene_volume", 0.35)) if acc else 0.35
    try:
        with ctx.db.begin_nested():
            generate_voiceover(ctx, project.id, scene_volume=volume, actor_check=False)
    except AppError as e:
        project.last_error = f"Lồng tiếng tự động lỗi: {e.message}"[:2000]
        log.warning("auto voiceover %s: %s", project.code, e.message)


def _after_scene_change(ctx: Ctx, project) -> None:
    """Tổng hợp trạng thái cảnh → chuyển trạng thái dự án."""
    from app.modules.generation.models import GenerationJob
    from app.modules.projects.models import Project
    from app.modules.scripts.models import Scene
    from app.workflows import state_machine as sm

    db = ctx.db
    db.flush()
    project = db.scalar(select(Project).where(Project.id == project.id).with_for_update(key_share=True))
    if project.status not in ("GENERATING", "GENERATION_QUEUED", "NEEDS_MANUAL_ACTION", "SCENE_QC", "FINAL_QC"):
        return
    scenes = db.scalars(select(Scene).where(Scene.project_id == project.id)).all()
    active = db.scalar(select(func.count()).select_from(GenerationJob).where(
        GenerationJob.project_id == project.id, GenerationJob.status.in_(["QUEUED", "SUBMITTED", "RUNNING", "RETRY_PENDING"])))
    done = all(s.status in ("GENERATED", "QC_PASSED") and s.selected_asset_id for s in scenes)
    if done and not active:
        if project.status == "NEEDS_MANUAL_ACTION":
            sm.transition(ctx, project, "GENERATING", note="Đủ cảnh sau thao tác thủ công")
        if project.status == "GENERATION_QUEUED":
            sm.transition(ctx, project, "GENERATING", note="Bắt đầu")
        if project.status == "GENERATING":
            sm.transition(ctx, project, "SCENE_QC", note="Đã tạo đủ cảnh — QC từng cảnh")
        if project.status in ("SCENE_QC", "FINAL_QC"):
            from app.modules.quality.service import run_scene_qc

            if project.status == "FINAL_QC":
                sm.transition(ctx, project, "SCENE_QC", note="Cảnh được tạo lại — QC lại")
            result = run_scene_qc(ctx, project)
            if result["all_passed"] and project.automation_level != "MANUAL":
                from app.modules.rendering.service import start_render, sync_timeline_clips

                sync_timeline_clips(ctx, project)  # timeline đã lưu phải dùng clip mới của cảnh vừa tạo lại
                project.last_error = None
                if project.automation_level == "AUTO":
                    _auto_voiceover(ctx, project)
                start_render(ctx, project, timeline=None, actor_check=False)
        return
    if active:
        return
    blocked = [s for s in scenes if s.status in ("GENERATION_FAILED", "NEEDS_MANUAL")]
    if blocked and project.status in ("GENERATING", "GENERATION_QUEUED"):
        reasons = []
        for s in blocked:
            last = db.scalar(select(GenerationJob).where(GenerationJob.scene_id == s.id).order_by(GenerationJob.created_at.desc()))
            reasons.append(f"Cảnh {s.order_index + 1}: {last.error_message if last and last.error_message else s.status}")
        project.last_error = "; ".join(reasons)[:2000]
        sm.transition(ctx, project, "NEEDS_MANUAL_ACTION", note=project.last_error)


# ====================== RENDER ======================
def run_render_job(job_id: str) -> str:
    from app.modules.rendering.models import RenderJob

    db = SessionLocal()
    try:
        job = db.scalar(select(RenderJob).where(RenderJob.id == job_id).with_for_update(skip_locked=True))
        if job is None or job.status in TERMINAL:
            return job.status if job else "MISSING"
        if job.status == "RUNNING" and job.started_at and job.started_at > _now() - timedelta(minutes=30):
            return "RUNNING"  # đang chạy ở worker khác
        job.status = "RUNNING"
        job.started_at = _now()
        _log(job, f"Bắt đầu render lần {job.attempt_no}")
        db.commit()
        job = db.get(RenderJob, job_id)
        try:
            from app.modules.rendering.service import execute_render

            execute_render(db, job)
        except Exception as e:  # noqa: BLE001 — mọi lỗi render đều phải được ghi nhận
            db.rollback()
            job = db.get(RenderJob, job_id)
            _render_failed(db, job, f"{type(e).__name__}: {e}")
        db.commit()
        return job.status
    finally:
        db.close()


def _render_failed(db, job, message: str) -> None:
    from app.modules.projects.models import Project
    from app.workflows import state_machine as sm

    ctx = _agent_ctx(db, job.data_mode, "A06")
    job.error_message = message[:2000]
    _log(job, f"Lỗi: {message}")
    project = db.get(Project, job.project_id)
    if job.attempt_no <= job.max_retries:
        job.attempt_no += 1
        job.status = "QUEUED"
        defer(db, "anngan.render.run_job", str(job.id))
        return
    job.status = "FAILED"
    job.finished_at = _now()
    if project.status == "RENDERING":
        project.last_error = message[:2000]
        sm.transition(ctx, project, "FAILED", note=f"Render thất bại sau {job.attempt_no} lần: {message[:300]}")


# ====================== RECOVERY ======================
def recover_stuck_jobs(older_than_minutes: int = 10) -> dict:
    """Gửi lại tác vụ bị kẹt (worker restart / broker mất kết nối). An toàn vì tác vụ idempotent."""
    from app.agents.runner import sweep_abandoned
    from app.modules.generation.models import GenerationJob
    from app.modules.rendering.models import RenderJob
    from app.workflows.celery_client import enqueue

    db = SessionLocal()
    try:
        cutoff = _now() - timedelta(minutes=older_than_minutes)
        gen = db.scalars(select(GenerationJob).where(GenerationJob.status.in_(["QUEUED", "SUBMITTED", "RUNNING"]),
                                                     GenerationJob.updated_at < cutoff)).all()
        ren = db.scalars(select(RenderJob).where(RenderJob.status.in_(["QUEUED", "RUNNING"]), RenderJob.updated_at < cutoff)).all()
        for r in ren:
            if r.status == "RUNNING":
                r.status = "QUEUED"
                _log(r, "Khôi phục sau khi worker dừng")
        abandoned = sweep_abandoned(db)
        db.commit()
        gen_ids, ren_ids = [str(j.id) for j in gen], [str(j.id) for j in ren]
    finally:
        db.close()
    for jid in gen_ids:
        enqueue("anngan.generation.run_job", jid)
    for jid in ren_ids:
        enqueue("anngan.render.run_job", jid)
    return {"generation": len(gen_ids), "render": len(ren_ids), "abandoned_agent_runs": abandoned}


def tmp_path(suffix: str) -> str:
    from app.media.storage import tmp_dir

    fd, path = tempfile.mkstemp(dir=tmp_dir(), suffix=suffix)
    os.close(fd)
    return path
