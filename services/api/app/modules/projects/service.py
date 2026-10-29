"""B01 — Project Manager service."""
import math
import uuid
from decimal import Decimal

from app.core import audit
from app.core.codes import next_code
from app.core.context import Ctx
from app.core.errors import NotFound, ValidationFailed
from app.modules.administration.models import User
from app.modules.administration.service import get_setting
from app.modules.projects.models import Channel, ProductionBatch, Project, WorkflowEvent
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate
from app.providers.video.registry import get_video_provider, list_video_providers
from app.workflows import state_machine as sm
from sqlalchemy import func, or_, select


def get_project(ctx: Ctx, project_id) -> Project:
    p = ctx.db.get(Project, project_id)
    if p is None or p.deleted_at is not None or p.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy dự án")
    return p


def lock_project(ctx: Ctx, project_id) -> Project:
    """SELECT ... FOR UPDATE để tránh hai thao tác đồng thời đổi trạng thái."""
    p = ctx.db.scalar(select(Project).where(Project.id == project_id).with_for_update(key_share=True))
    if p is None or p.deleted_at is not None or p.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy dự án")
    return p


def _validate_refs(ctx: Ctx, data) -> list[str]:
    from app.modules.characters.models import Character, SceneLock, VoiceProfile

    warnings = []
    for cid in data.character_ids or []:
        c = ctx.db.get(Character, cid)
        if c is None or c.deleted_at or c.data_mode != ctx.mode:
            raise ValidationFailed(f"Nhân vật {cid} không tồn tại", code="INVALID_CHARACTER")
        if c.status != "LOCKED":
            warnings.append(f"Nhân vật {c.name} chưa có Character Lock được duyệt")
    for sid in getattr(data, "scene_lock_ids", None) or []:
        s = ctx.db.get(SceneLock, sid)
        if s is None or s.data_mode != ctx.mode:
            raise ValidationFailed(f"Scene Lock {sid} không tồn tại", code="INVALID_SCENE_LOCK")
    if data.voice_profile_id:
        v = ctx.db.get(VoiceProfile, data.voice_profile_id)
        if v is None or v.deleted_at or v.data_mode != ctx.mode:
            raise ValidationFailed("Voice Profile không tồn tại", code="INVALID_VOICE")
        if v.consent_status != "GRANTED":
            warnings.append(f"Giọng {v.name} chưa có xác nhận đồng ý sử dụng (consent)")
    if getattr(data, "owner_id", None):
        u = ctx.db.get(User, data.owner_id)
        if u is None or not u.is_active:
            raise ValidationFailed("Người phụ trách không hợp lệ")
    return warnings


def estimate(ctx: Ctx, *, duration_sec: int, quantity: int, provider_code: str, budget_limit: Decimal) -> dict:
    policy = get_setting(ctx.db, "generation.policy")
    scene_sec = int(policy.get("scene_seconds", 8))
    scenes = math.ceil(duration_sec / scene_sec)
    provider = get_video_provider(ctx.db, provider_code, ctx.mode)
    per_scene = Decimal(provider.unit_cost_vnd_per_sec) * scene_sec
    per_video = per_scene * scenes
    retry_buffer = per_video * Decimal("0.3")
    return {
        "scene_count": scenes, "scene_seconds": scene_sec, "duration_sec": scenes * scene_sec,
        "provider": provider.code, "provider_kind": provider.kind, "simulated": not provider.is_real,
        "cost_per_scene": float(per_scene), "cost_per_video": float(per_video),
        "cost_per_video_with_retry_buffer": float(per_video + retry_buffer),
        "total_estimate": float(per_video * quantity),
        "within_budget": (budget_limit == 0) or (per_video <= budget_limit),
    }


def create_projects(ctx: Ctx, data: ProjectCreate) -> dict:
    ctx.require("project.create")
    db = ctx.db
    # Idempotency: cùng key → trả về kết quả cũ, không tạo trùng
    if data.idempotency_key:
        if data.quantity == 1:
            existing = db.scalar(select(Project).where(Project.idempotency_key == data.idempotency_key))
            if existing:
                return {"projects": [existing], "batch_id": existing.batch_id, "duplicate": True, "estimate": {}, "warnings": []}
        else:
            batch = db.scalar(select(ProductionBatch).where(ProductionBatch.idempotency_key == data.idempotency_key))
            if batch:
                items = db.scalars(select(Project).where(Project.batch_id == batch.id).order_by(Project.code)).all()
                return {"projects": items, "batch_id": batch.id, "duplicate": True, "estimate": {}, "warnings": []}
    channel = db.get(Channel, data.channel_id)
    if channel is None or not channel.is_active or channel.deleted_at:
        raise ValidationFailed("Kênh không tồn tại hoặc đã ngừng", code="INVALID_CHANNEL")
    warnings = _validate_refs(ctx, data)
    est = estimate(ctx, duration_sec=data.duration_sec, quantity=data.quantity, provider_code=data.video_provider_code,
                   budget_limit=data.budget_limit)
    if not est["within_budget"]:
        warnings.append(f"Chi phí ước tính {est['cost_per_video']:,.0f} VND/video vượt ngân sách dự án "
                        f"{data.budget_limit:,.0f} VND — tác vụ tạo cảnh sẽ bị chặn khi vượt.")
    batch = None
    if data.quantity > 1:
        batch = ProductionBatch(code=next_code(db, ProductionBatch, "LOT"), channel_id=channel.id,
                                title=data.title or data.topic[:120], quantity=data.quantity,
                                created_by=ctx.actor.user_uuid, idempotency_key=data.idempotency_key, data_mode=ctx.mode)
        db.add(batch)
        db.flush()
    projects = []
    for i in range(data.quantity):
        code = next_code(db, Project, "PRJ")
        title = data.title or data.topic[:120]
        if data.quantity > 1:
            title = f"{title} #{i + 1}"
        key = data.idempotency_key if data.quantity == 1 else (f"{data.idempotency_key}:{i}" if data.idempotency_key else None)
        p = Project(
            code=code, channel_id=channel.id, batch_id=batch.id if batch else None, title=title, topic=data.topic,
            objective=data.objective, target_audience=data.target_audience, duration_sec=est["duration_sec"],
            style=data.style, setting=data.setting, cta=data.cta, character_ids=[str(c) for c in data.character_ids],
            scene_lock_ids=[str(s) for s in data.scene_lock_ids], voice_profile_id=data.voice_profile_id,
            budget_limit=data.budget_limit, automation_level=data.automation_level,
            video_provider_code=data.video_provider_code, owner_id=data.owner_id or ctx.actor.user_uuid,
            created_by=ctx.actor.user_uuid, deadline=data.deadline, priority=data.priority, idempotency_key=key,
            data_mode=ctx.mode, status="CREATED", progress=0,
        )
        db.add(p)
        db.flush()
        db.add(WorkflowEvent(project_id=p.id, from_status=None, to_status="CREATED", actor_type=ctx.actor.type,
                             actor_ref=ctx.actor.id, note="Khởi tạo từ Trung tâm tạo video", payload={"estimate": est}))
        audit.record(ctx, "project.create", "project", p.id, after={"code": code, "title": title, "channel": channel.code})
        projects.append(p)
    return {"projects": projects, "batch_id": batch.id if batch else None, "duplicate": False, "estimate": est,
            "warnings": warnings}


def list_projects(ctx: Ctx, *, status=None, channel_id=None, owner_id=None, q=None, batch_id=None, page=1, page_size=50,
                  date_from=None, date_to=None):
    stmt = select(Project).where(Project.data_mode == ctx.mode, Project.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Project.status.in_(status.split(",")))
    if channel_id:
        stmt = stmt.where(Project.channel_id == channel_id)
    if owner_id:
        stmt = stmt.where(Project.owner_id == owner_id)
    if batch_id:
        stmt = stmt.where(Project.batch_id == batch_id)
    if date_from:
        stmt = stmt.where(Project.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Project.created_at <= date_to)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Project.title.ilike(like), Project.code.ilike(like), Project.topic.ilike(like)))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = ctx.db.scalars(stmt.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def kanban(ctx: Ctx, channel_id=None) -> dict:
    stmt = select(Project).where(Project.data_mode == ctx.mode, Project.deleted_at.is_(None))
    if channel_id:
        stmt = stmt.where(Project.channel_id == channel_id)
    columns = {
        "Khởi tạo & Kịch bản": ["CREATED", "SCRIPT_GENERATING", "SCRIPT_REVIEW", "STORYBOARD_READY"],
        "Sản xuất": ["ASSET_VALIDATION", "GENERATION_QUEUED", "GENERATING", "SCENE_QC", "RENDERING"],
        "Kiểm định & Duyệt": ["FINAL_QC", "APPROVAL_PENDING", "APPROVED"],
        "Phát hành & Theo dõi": ["PUBLISH_QUEUED", "PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW"],
        "Cần xử lý": ["FAILED", "RETRY_PENDING", "NEEDS_MANUAL_ACTION"],
        "Đã huỷ": ["CANCELLED"],
    }
    items = ctx.db.scalars(stmt.order_by(Project.updated_at.desc()).limit(500)).all()
    out = {name: [] for name in columns}
    for p in items:
        for name, states in columns.items():
            if p.status in states:
                out[name].append(p)
                break
    return {"columns": [{"name": n, "statuses": columns[n], "items": out[n]} for n in columns]}


def _switch_video_provider(ctx: Ctx, p: Project, code: str) -> None:
    """Đổi nhà cung cấp video: chặn khi còn tác vụ đang chạy; huỷ các tác vụ đang chờ thủ công của provider cũ."""
    from app.modules.generation.models import GenerationJob
    from app.modules.scripts.models import Scene

    provider = get_video_provider(ctx.db, code, ctx.mode)
    info = next((x for x in list_video_providers(ctx.db, ctx.mode) if x["code"] == code), None)
    if info is None or not info["available"]:
        raise ValidationFailed(f"Nhà cung cấp {provider.name} chưa sẵn sàng — nhập API key & bật ở M15", code="PROVIDER_NOT_READY")
    running = ctx.db.scalar(select(GenerationJob.id).where(
        GenerationJob.project_id == p.id, GenerationJob.status.in_(["QUEUED", "SUBMITTED", "RUNNING", "RETRY_PENDING"])).limit(1))
    if running is not None:
        raise ValidationFailed("Đang có cảnh được tạo — chờ xong hoặc huỷ tác vụ rồi mới đổi nhà cung cấp", code="JOBS_RUNNING")
    waiting = list(ctx.db.scalars(select(GenerationJob).where(
        GenerationJob.project_id == p.id, GenerationJob.status == "NEEDS_MANUAL_ACTION")))
    for job in waiting:
        job.status = "CANCELLED"
        job.log = [*(job.log or []), {"msg": f"Huỷ do đổi nhà cung cấp sang {provider.name}"}]
        scene = ctx.db.get(Scene, job.scene_id)
        if scene is not None and scene.status not in ("GENERATED", "QC_PASSED"):
            scene.status = "PROMPT_READY"


def update_project(ctx: Ctx, project_id, data: ProjectUpdate) -> Project:
    ctx.require("project.edit")
    p = lock_project(ctx, project_id)
    if p.status in ("CANCELLED", "PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW"):
        raise ValidationFailed("Dự án đã kết thúc, không thể sửa")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("automation_level") and changes["automation_level"] not in {"MANUAL", "ASSISTED", "AUTO"}:
        raise ValidationFailed("Mức tự động hoá không hợp lệ")
    if "video_provider_code" in changes and changes["video_provider_code"] != p.video_provider_code:
        _switch_video_provider(ctx, p, changes["video_provider_code"])
    elif "video_provider_code" in changes:
        changes.pop("video_provider_code")
    _validate_refs(ctx, data)
    before = {k: getattr(p, k) for k in changes}
    for k, v in changes.items():
        if k == "character_ids":
            v = [str(x) for x in v]
        setattr(p, k, v)
    audit.record(ctx, "project.update", "project", p.id, before=before, after=changes)
    return p


def cancel_project(ctx: Ctx, project_id, note: str) -> Project:
    ctx.require("project.cancel")
    p = lock_project(ctx, project_id)
    from app.modules.generation.models import GenerationJob

    sm.transition(ctx, p, "CANCELLED", note=note or "Huỷ dự án")
    for job in ctx.db.scalars(select(GenerationJob).where(GenerationJob.project_id == p.id,
                                                         GenerationJob.status.in_(["QUEUED", "SUBMITTED", "RUNNING", "RETRY_PENDING", "NEEDS_MANUAL_ACTION"]))):
        job.status = "CANCELLED"
    return p


def events(ctx: Ctx, project_id) -> list[WorkflowEvent]:
    get_project(ctx, project_id)
    return ctx.db.scalars(select(WorkflowEvent).where(WorkflowEvent.project_id == project_id)
                          .order_by(WorkflowEvent.created_at)).all()


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
