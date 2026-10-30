"""B05 — Video Generation Manager."""
import uuid
from decimal import Decimal

from app.agents.runner import run_agent
from app.core import audit
from app.core.context import Ctx
from app.core.errors import Conflict, InvalidTransition, NotFound, ValidationFailed
from app.media.models import Asset
from app.modules.administration import service as admin
from app.modules.administration.service import get_setting
from app.modules.characters.models import Character, CharacterLock, SceneLock, VoiceProfile
from app.modules.generation.models import GenerationJob
from app.modules.projects.models import Project
from app.modules.projects.service import get_project, lock_project
from app.modules.scripts.models import Scene
from app.providers.video.base import GenerationSpec
from app.providers.video.registry import get_video_provider
from app.workflows import state_machine as sm
from app.workflows.dispatch import defer
from sqlalchemy import func, select

ACTIVE = ["QUEUED", "SUBMITTED", "RUNNING", "RETRY_PENDING"]


def _scenes(ctx: Ctx, p: Project) -> list[Scene]:
    return ctx.db.scalars(select(Scene).where(Scene.project_id == p.id).order_by(Scene.order_index)).all()


def validate_assets(ctx: Ctx, project_id) -> dict:
    """A04 AI Character: kiểm tra Lock, consent, tài nguyên, năng lực provider trước khi tạo cảnh."""
    ctx.require("generation.run")
    p = lock_project(ctx, project_id)
    if p.status == "STORYBOARD_READY":
        sm.transition(ctx, p, "ASSET_VALIDATION", note="A04 kiểm tra tài nguyên")
    elif p.status not in ("ASSET_VALIDATION", "NEEDS_MANUAL_ACTION"):
        raise InvalidTransition(f"Không thể kiểm tra tài nguyên ở trạng thái {p.status}")
    elif p.status == "NEEDS_MANUAL_ACTION":
        sm.transition(ctx, p, "ASSET_VALIDATION", note="Kiểm tra lại sau thao tác thủ công")
    scenes = _scenes(ctx, p)
    provider = get_video_provider(ctx.db, p.video_provider_code, ctx.mode)

    def work(_llm, actx):
        blocking, warnings = [], []
        if not scenes:
            blocking.append("Chưa có cảnh")
        char_ids = {str(c) for c in (p.character_ids or [])} | {str(c) for s in scenes for c in (s.character_ids or [])}
        for cid in char_ids:
            c = ctx.db.get(Character, uuid.UUID(cid))
            if c is None or c.deleted_at:
                blocking.append(f"Nhân vật {cid} không tồn tại")
                continue
            lock = ctx.db.get(CharacterLock, c.active_lock_id) if c.active_lock_id else None
            if lock is None or lock.status != "APPROVED":
                blocking.append(f"{c.code} {c.name}: chưa có Character Lock được duyệt")
            else:
                for ref_type, ref in (lock.lock_data.get("references") or {}).items():
                    a = ctx.db.get(Asset, uuid.UUID(ref["asset_id"]))
                    if a is None or a.deleted_at:
                        blocking.append(f"{c.code}: ảnh {ref_type} trong Lock đã bị xoá")
                    elif a.checksum_sha256 != ref.get("checksum"):
                        blocking.append(f"{c.code}: ảnh {ref_type} không khớp checksum của Lock")
            if c.consent_status in ("PENDING", "REVOKED"):
                blocking.append(f"{c.code}: chưa có consent sử dụng hình ảnh")
        if p.voice_profile_id:
            v = ctx.db.get(VoiceProfile, p.voice_profile_id)
            if v is None or v.consent_status != "GRANTED":
                blocking.append("Giọng nói chưa có consent")
            elif not v.active_lock_id:
                warnings.append(f"Giọng {v.name} chưa có Voice Lock")
        for sid in p.scene_lock_ids or []:
            sl = ctx.db.get(SceneLock, uuid.UUID(sid))
            if sl is None or sl.status != "APPROVED":
                blocking.append(f"Scene Lock {sid} chưa được duyệt")
        for s in scenes:
            if not s.prompt_text.strip():
                blocking.append(f"Cảnh {s.order_index + 1}: chưa có prompt")
            spec = GenerationSpec(job_ref="check", prompt_text=s.prompt_text or "x", duration_sec=s.duration_sec,
                                  aspect_ratio=p.aspect_ratio)
            blocking += [f"Cảnh {s.order_index + 1}: {i}" for i in provider.validate_capabilities(spec)]
        est = sum((provider.estimate_cost(GenerationSpec(job_ref="e", prompt_text="x", duration_sec=s.duration_sec))
                   for s in scenes if s.status not in ("GENERATED", "QC_PASSED")), Decimal(0))
        budget = admin.check_budget(ctx, estimated=est, project=p, provider_code=provider.code, raise_on_exceed=False)
        if not budget["allowed"]:
            blocking.append(f"Chi phí ước tính {est:,.0f} VND vượt ngân sách")
        return {"result": {"blocking": blocking, "warnings": warnings, "estimated_cost": float(est),
                           "provider": provider.info(), "budget_allowed": budget["allowed"]}}, None

    run = run_agent(ctx, "A04", "assets.validate", work, project=p, input_ref={"project": p.code})
    report = run.output["result"]
    if report["blocking"]:
        p.last_error = "; ".join(report["blocking"])[:2000]
        sm.transition(ctx, p, "NEEDS_MANUAL_ACTION", note="Thiếu điều kiện: " + p.last_error[:500], payload=report)
    else:
        sm.transition(ctx, p, "GENERATION_QUEUED", note="Tài nguyên hợp lệ", payload=report)
    return report


def _voided_manual_count(ctx: Ctx, scene: Scene) -> int:
    """Tác vụ chờ nhập Flow đã huỷ (vd. do đổi nhà cung cấp): không tốn phí, không tính vào giới hạn lần tạo."""
    return ctx.db.scalar(select(func.count()).select_from(GenerationJob).where(
        GenerationJob.scene_id == scene.id, GenerationJob.scene_version_no == scene.current_version_no,
        GenerationJob.provider_code == "manual_flow", GenerationJob.status == "CANCELLED")) or 0


def _attempts_for_scene_version(ctx: Ctx, scene: Scene) -> int:
    total = ctx.db.scalar(select(func.count()).select_from(GenerationJob).where(
        GenerationJob.scene_id == scene.id, GenerationJob.scene_version_no == scene.current_version_no)) or 0
    return total - _voided_manual_count(ctx, scene)


def _new_job(ctx: Ctx, p: Project, scene: Scene, provider, *, manual_retry: bool = False) -> GenerationJob:
    policy = get_setting(ctx.db, "generation.policy")
    max_retries = int(policy.get("max_retries", 3))
    active = ctx.db.scalar(select(GenerationJob).where(GenerationJob.scene_id == scene.id, GenerationJob.status.in_(ACTIVE)))
    if active is not None:
        raise Conflict(f"Cảnh {scene.order_index + 1} đang có tác vụ chạy", code="DUPLICATE_JOB",
                       details={"job_id": str(active.id)})
    attempts = _attempts_for_scene_version(ctx, scene)
    if attempts >= max_retries + 1:
        raise ValidationFailed(f"Cảnh {scene.order_index + 1} đã tạo {attempts} lần (giới hạn {max_retries + 1}/phiên bản). "
                               "Hãy sửa prompt/cảnh để tạo phiên bản mới.", code="RETRY_LIMIT")
    if not scene.prompt_text.strip():
        raise ValidationFailed(f"Cảnh {scene.order_index + 1} chưa có prompt", code="MISSING_PROMPT")
    spec = GenerationSpec(job_ref=str(scene.id), prompt_text=scene.prompt_text, duration_sec=scene.duration_sec,
                          aspect_ratio=p.aspect_ratio)
    est = provider.estimate_cost(spec)
    # Số lần đánh lại sau khi bỏ tác vụ Flow đã huỷ → thêm tiền tố x<n> để khoá idempotency không trùng bản cũ
    voided = _voided_manual_count(ctx, scene)
    key_base = f"{scene.id}:v{scene.current_version_no}" + (f":x{voided}" if voided else "")
    job = GenerationJob(
        project_id=p.id, scene_id=scene.id, scene_version_no=scene.current_version_no, provider_code=provider.code,
        status="QUEUED", attempt_no=attempts + 1, max_retries=max_retries, estimated_cost=est,
        prompt_snapshot={"prompt_text": scene.prompt_text, "negative_prompt": scene.negative_prompt,
                         "prompt_parts": scene.prompt_parts, "prompt_version_id": str(scene.prompt_version_id) if scene.prompt_version_id else None},
        idempotency_key=f"{key_base}:a{attempts + 1}", requested_by=ctx.actor.user_uuid,
        data_mode=ctx.mode, log=[{"msg": "Thủ công tạo lại" if manual_retry else "Xếp hàng"}],
    )
    ctx.db.add(job)
    ctx.db.flush()
    scene.status = "GENERATING"
    return job


def queue_generation(ctx: Ctx, project_id, scene_ids: list | None = None) -> list[GenerationJob]:
    ctx.require("generation.run")
    p = lock_project(ctx, project_id)
    if p.status not in ("GENERATION_QUEUED", "GENERATING", "SCENE_QC", "FINAL_QC", "NEEDS_MANUAL_ACTION", "RETRY_PENDING"):
        raise InvalidTransition(f"Không thể tạo cảnh ở trạng thái {p.status}")
    if p.status == "NEEDS_MANUAL_ACTION" and not ctx.db.scalar(
            select(GenerationJob.id).where(GenerationJob.project_id == p.id).limit(1)):
        raise InvalidTransition("Dự án chưa qua kiểm tra tài nguyên — xử lý vấn đề rồi chạy lại 'Kiểm tra tài nguyên'",
                                code="ASSET_VALIDATION_REQUIRED")
    provider = get_video_provider(ctx.db, p.video_provider_code, ctx.mode)
    scenes = _scenes(ctx, p)
    targets = [s for s in scenes if (scene_ids and str(s.id) in {str(x) for x in scene_ids})
               or (not scene_ids and s.status not in ("GENERATED", "QC_PASSED"))]
    if not targets:
        raise ValidationFailed("Không có cảnh nào cần tạo")
    est_total = sum((provider.estimate_cost(GenerationSpec(job_ref="e", prompt_text="x", duration_sec=s.duration_sec))
                     for s in targets), Decimal(0))
    admin.check_budget(ctx, estimated=est_total, project=p, provider_code=provider.code)
    jobs = [_new_job(ctx, p, s, provider, manual_retry=bool(scene_ids)) for s in targets]
    target_state = "GENERATING"
    if p.status == "RETRY_PENDING":
        sm.transition(ctx, p, "GENERATING", note="Chạy lại tạo cảnh")
    elif p.status != target_state:
        sm.transition(ctx, p, target_state, note=f"A05 gửi {len(jobs)} cảnh tới {provider.name}")
    for j in jobs:
        defer(ctx.db, "anngan.generation.run_job", str(j.id))
    audit.record(ctx, "generation.queue", "project", p.id, after={"jobs": len(jobs), "provider": provider.code,
                                                                   "estimated": float(est_total)})
    return jobs


def cancel_job(ctx: Ctx, job_id) -> GenerationJob:
    ctx.require("generation.cancel")
    job = ctx.db.get(GenerationJob, job_id)
    if job is None or job.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy tác vụ")
    if job.status not in ACTIVE + ["NEEDS_MANUAL_ACTION"]:
        raise ValidationFailed("Tác vụ đã kết thúc")
    try:
        provider = get_video_provider(ctx.db, job.provider_code, ctx.mode)
        if job.provider_job_id:
            provider.cancel_job(job.provider_job_id)
    except Exception:
        pass
    job.status = "CANCELLED"
    scene = ctx.db.get(Scene, job.scene_id)
    if scene and scene.status == "GENERATING":
        scene.status = "PROMPT_READY"
    audit.record(ctx, "generation.cancel", "generation_job", job.id)
    from app.workflows.jobs import _after_scene_change

    _after_scene_change(ctx, ctx.db.get(Project, job.project_id))
    return job


def import_flow_clip(ctx: Ctx, scene_id, path: str, filename: str, actual_cost: Decimal = Decimal(0), note: str = "") -> dict:
    """Nhập clip tạo trên Google Flow: kiểm tra định dạng → gắn Scene ID → hoàn tất tác vụ manual."""
    from app.media.probe import ffprobe, summarize
    from app.media.service import ingest_file
    from app.providers.video.manual_flow import validate_flow_clip

    ctx.require("generation.import")
    scene = ctx.db.get(Scene, scene_id)
    if scene is None or scene.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy cảnh")
    p = lock_project(ctx, scene.project_id)
    if p.status not in ("GENERATION_QUEUED", "GENERATING", "NEEDS_MANUAL_ACTION", "SCENE_QC", "FINAL_QC"):
        raise InvalidTransition(f"Không thể nhập cảnh ở trạng thái {p.status}")
    info = summarize(ffprobe(path))
    errors, warnings = validate_flow_clip(info, p.aspect_ratio, scene.duration_sec)
    if errors:
        raise ValidationFailed("Clip Flow không đạt yêu cầu", code="INVALID_FLOW_CLIP", details={"errors": errors, "media": info})
    asset = ingest_file(ctx, path, filename, asset_type="VIDEO", source="MANUAL_FLOW", usage_rights="AI_GENERATED",
                        tags=["scene", "google_flow", p.code], channel_id=p.channel_id, project_id=p.id, scene_id=scene.id,
                        extra_info={"flow_import": True, "warnings": warnings}, rights_note=note or "Nhập từ Google Flow")
    job = ctx.db.scalar(select(GenerationJob).where(GenerationJob.scene_id == scene.id,
                                                    GenerationJob.status.in_(ACTIVE + ["NEEDS_MANUAL_ACTION"]))
                        .order_by(GenerationJob.created_at.desc()))
    if job is None:
        n = _attempts_for_scene_version(ctx, scene) + 1
        job = GenerationJob(project_id=p.id, scene_id=scene.id, scene_version_no=scene.current_version_no,
                            provider_code="manual_flow", status="NEEDS_MANUAL_ACTION", attempt_no=n, max_retries=0,
                            prompt_snapshot={"prompt_text": scene.prompt_text}, data_mode=ctx.mode,
                            idempotency_key=f"{scene.id}:v{scene.current_version_no}:flow:{uuid.uuid4().hex[:8]}",
                            requested_by=ctx.actor.user_uuid)
        ctx.db.add(job)
        ctx.db.flush()
    job.status = "SUCCEEDED"
    job.result_asset_id = asset.id
    job.actual_cost = actual_cost
    job.log = [*(job.log or []), {"msg": f"Nhập thủ công từ Flow bởi {ctx.actor.label}", "warnings": warnings}]
    if actual_cost > 0:
        admin.record_cost(ctx.db, ctx.mode, category="VIDEO_GEN", provider_code="manual_flow", amount=actual_cost,
                          quantity=Decimal(scene.duration_sec), project=p, scene_id=scene.id, generation_job_id=job.id,
                          is_simulated=False, description="Chi phí Flow nhập tay")
    scene.selected_asset_id = asset.id
    scene.status = "GENERATED"
    audit.record(ctx, "generation.flow_import", "scene", scene.id, after={"asset": str(asset.id), "warnings": warnings})
    if p.status == "GENERATION_QUEUED":
        sm.transition(ctx, p, "GENERATING", note="Bắt đầu nhận cảnh từ Flow")
    from app.workflows.jobs import _after_scene_change

    _after_scene_change(ctx, p)
    return {"asset_id": str(asset.id), "job_id": str(job.id), "warnings": warnings, "media": info}


def select_scene_version(ctx: Ctx, scene_id, asset_id) -> Scene:
    """Chọn lại một kết quả đã tạo trước đó (quản lý phiên bản cảnh)."""
    ctx.require("generation.run")
    scene = ctx.db.get(Scene, scene_id)
    if scene is None or scene.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy cảnh")
    a = ctx.db.get(Asset, asset_id)
    if a is None or a.scene_id != scene.id or a.deleted_at:
        raise ValidationFailed("Asset không thuộc cảnh này")
    scene.selected_asset_id = a.id
    scene.status = "GENERATED"
    audit.record(ctx, "scene.select_asset", "scene", scene.id, after={"asset": str(a.id)})
    return scene


def list_jobs(ctx: Ctx, *, project_id=None, status=None, page=1, page_size=100):
    stmt = select(GenerationJob).where(GenerationJob.data_mode == ctx.mode)
    if project_id:
        stmt = stmt.where(GenerationJob.project_id == project_id)
    if status:
        stmt = stmt.where(GenerationJob.status.in_(status.split(",")))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = ctx.db.scalars(stmt.order_by(GenerationJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def scene_production(ctx: Ctx, project_id) -> list[dict]:
    p = get_project(ctx, project_id)
    out = []
    for s in _scenes(ctx, p):
        jobs = ctx.db.scalars(select(GenerationJob).where(GenerationJob.scene_id == s.id).order_by(GenerationJob.created_at.desc())).all()
        outputs = ctx.db.scalars(select(Asset).where(Asset.scene_id == s.id, Asset.asset_type == "VIDEO",
                                                     Asset.deleted_at.is_(None)).order_by(Asset.created_at.desc())).all()
        out.append({"scene": s, "jobs": jobs, "outputs": outputs,
                    "attempts_this_version": _attempts_for_scene_version(ctx, s),
                    "cost_total": float(sum((j.actual_cost for j in jobs), Decimal(0)))})
    return out
