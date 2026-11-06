"""B12 API — Cài đặt & quản trị hệ thống (M15)."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.api.deps import require
from app.api.schemas import ORM, Email, Page
from app.core import audit
from app.core.context import Ctx
from app.core.errors import NotFound, ValidationFailed
from app.core.security import encrypt_secret, mask_secret
from app.modules.administration import backup, service
from app.modules.administration.models import (
    AuditLog,
    BackupRecord,
    BudgetLimit,
    CostRecord,
    Notification,
    Permission,
    ProviderAccount,
    Role,
    User,
)
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

router = APIRouter(prefix="/admin", tags=["B12 Administration & Cost Manager"])


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    is_demo: bool
    created_at: datetime


class UserIn(BaseModel):
    email: Email
    full_name: str = Field(min_length=2, max_length=160)
    role_code: str
    password: str = Field(min_length=10, max_length=200)


class UserPatch(BaseModel):
    full_name: str | None = None
    role_code: str | None = None
    is_active: bool | None = None


class ProviderOut(ORM):
    id: uuid.UUID
    provider_type: str
    provider_code: str
    name: str
    is_enabled: bool
    config: dict
    secret_last4: str | None
    connection_status: str
    last_verified_at: datetime | None
    last_error: str | None
    unit_cost: Decimal
    cost_unit: str


class ProviderPatch(BaseModel):
    is_enabled: bool | None = None
    config: dict | None = None
    api_key: str | None = Field(default=None, min_length=8, max_length=4000)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    clear_api_key: bool = False


class BudgetOut(ORM):
    id: uuid.UUID
    scope: str
    scope_ref: str
    period: str
    limit_amount: Decimal
    alert_threshold_pct: int
    hard_stop: bool
    data_mode: str


class BudgetIn(BaseModel):
    scope: str
    scope_ref: str = "*"
    period: str = "MONTHLY"
    limit_amount: Decimal = Field(ge=0)
    alert_threshold_pct: int = Field(default=80, ge=1, le=100)
    hard_stop: bool = True


class ModeIn(BaseModel):
    mode: str
    confirm_text: str


class SettingIn(BaseModel):
    value: dict


class AuditOut(ORM):
    id: uuid.UUID
    created_at: datetime
    actor_type: str
    actor_id: str | None
    actor_label: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict | None
    after: dict | None
    ip_address: str | None
    data_mode: str


class NotificationOut(ORM):
    id: uuid.UUID
    level: str
    category: str
    title: str
    message: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class BackupIn(BaseModel):
    include_media: bool = False
    note: str = ""


class RestoreIn(BaseModel):
    file_name: str
    confirm_text: str


def _user_out(u: User) -> dict:
    return {**UserOut.model_validate(u).model_dump(mode="json"), "role": {"code": u.role.code, "name": u.role.name}}


# ---------- Users & roles ----------
@router.get("/users")
def users(ctx: Ctx = Depends(require("admin.users"))):
    return [_user_out(u) for u in ctx.db.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.email)).all()]


@router.get("/users/directory")
def directory(ctx: Ctx = Depends(require("project.view"))):
    """Danh bạ tối giản để chọn người phụ trách (không lộ thông tin nhạy cảm)."""
    return [{"id": str(u.id), "full_name": u.full_name, "role": u.role.code}
            for u in ctx.db.scalars(select(User).where(User.deleted_at.is_(None), User.is_active)).all()]


@router.post("/users", status_code=201)
def create_user(data: UserIn, ctx: Ctx = Depends(require("admin.users"))):
    u = service.create_user(ctx, email=data.email, full_name=data.full_name, role_code=data.role_code, password=data.password)
    ctx.db.commit()
    return _user_out(u)


@router.patch("/users/{uid}")
def update_user(uid: uuid.UUID, data: UserPatch, ctx: Ctx = Depends(require("admin.users"))):
    u = service.update_user(ctx, uid, **data.model_dump(exclude_unset=True))
    ctx.db.commit()
    return _user_out(u)


@router.get("/roles")
def roles(ctx: Ctx = Depends(require("admin.roles"))):
    perms = ctx.db.scalars(select(Permission).order_by(Permission.code)).all()
    return {"roles": [{"code": r.code, "name": r.name, "permissions": sorted(p.code for p in r.permissions)}
                      for r in ctx.db.scalars(select(Role).order_by(Role.code)).all()],
            "permissions": [{"code": p.code, "description": p.description} for p in perms]}


# ---------- Providers ----------
@router.get("/providers", response_model=list[ProviderOut])
def providers(ctx: Ctx = Depends(require("admin.providers"))):
    return ctx.db.scalars(select(ProviderAccount).order_by(ProviderAccount.provider_type, ProviderAccount.provider_code)).all()


@router.patch("/providers/{pid}", response_model=ProviderOut)
def update_provider(pid: uuid.UUID, data: ProviderPatch, ctx: Ctx = Depends(require("admin.providers"))):
    acc = ctx.db.get(ProviderAccount, pid)
    if acc is None:
        raise NotFound("Không tìm thấy nhà cung cấp")
    if acc.connection_status == "BUILTIN" and data.api_key:
        raise ValidationFailed("Provider tích hợp sẵn không cần API key")
    changes = {}
    if data.is_enabled is not None:
        acc.is_enabled = data.is_enabled
        changes["is_enabled"] = data.is_enabled
    if data.config is not None:
        if any(k.lower() in ("api_key", "token", "secret", "password") for k in data.config):
            raise ValidationFailed("Không lưu secret trong config — dùng trường api_key (được mã hoá)")
        acc.config = data.config
        changes["config"] = list(data.config)
    if data.unit_cost is not None:
        acc.unit_cost = data.unit_cost
        changes["unit_cost"] = float(data.unit_cost)
    if data.clear_api_key:
        acc.secret_encrypted = None
        acc.secret_last4 = None
        acc.is_enabled = False
        acc.connection_status = "NOT_CONFIGURED"
        acc.last_verified_at = None
        changes["api_key"] = "CLEARED"
    elif data.api_key:
        acc.secret_encrypted = encrypt_secret(data.api_key)
        acc.secret_last4 = mask_secret(data.api_key)
        acc.connection_status = "CONFIGURED_UNVERIFIED"
        acc.last_verified_at = None
        changes["api_key"] = "***"
    audit.record(ctx, "provider.update", "provider_account", acc.id, after=changes)
    ctx.db.commit()
    return acc


@router.post("/providers/{pid}/test", response_model=ProviderOut)
def test_provider(pid: uuid.UUID, ctx: Ctx = Depends(require("admin.providers"))):
    """Kiểm tra kết nối. Chỉ đánh dấu VERIFIED khi gọi API thật thành công."""
    from app.core.security import decrypt_secret

    acc = ctx.db.get(ProviderAccount, pid)
    if acc is None:
        raise NotFound("Không tìm thấy nhà cung cấp")
    if acc.connection_status == "BUILTIN":
        return acc
    key = decrypt_secret(acc.secret_encrypted) if acc.secret_encrypted else None
    if (acc.config or {}).get("adapter") in ("flow_cdp", "vieneu_local"):  # chạy trên máy, không cần key
        try:
            if acc.config["adapter"] == "flow_cdp":
                from app.providers.video.registry import build_real_provider

                build_real_provider(acc, None).test_connection()
            else:
                from app.providers.tts.vieneu_local import VieNeuLocalProvider

                VieNeuLocalProvider(config=acc.config).test_connection()
            acc.connection_status, acc.last_error, acc.last_verified_at = "VERIFIED", None, datetime.now(timezone.utc)
        except Exception as e:  # noqa: BLE001
            acc.connection_status, acc.last_error = "ERROR", str(e)[:500]
    elif not key:
        acc.connection_status = "NOT_CONFIGURED"
        acc.last_error = "Chưa có API key"
    elif acc.provider_code == "facebook_pages":  # đọc danh sách Fanpage — không đăng gì
        try:
            from app.modules.publishing import service as publishing
            from app.providers.publishing.base import FacebookPagesPublisher

            pages = FacebookPagesPublisher(key, acc.config, client=publishing._fb_http).pages()
            if not pages:
                raise ValueError("Token không quản lý Fanpage nào (cần quyền pages_manage_posts, pages_show_list)")
            acc.connection_status, acc.last_error, acc.last_verified_at = "VERIFIED", None, datetime.now(timezone.utc)
        except Exception as e:  # noqa: BLE001
            acc.connection_status, acc.last_error = "ERROR", str(e)[:500]
    elif acc.provider_code == "anthropic":
        if ctx.mode != "PRODUCTION":
            raise ValidationFailed("Kiểm tra kết nối LLM thật chỉ chạy ở PRODUCTION MODE (tránh phát sinh chi phí ở DEMO)")
        try:
            import anthropic

            anthropic.Anthropic(api_key=key, timeout=20, max_retries=0).models.retrieve(acc.config.get("model", "claude-opus-5-5"))
            acc.connection_status, acc.last_error, acc.last_verified_at = "VERIFIED", None, datetime.now(timezone.utc)
        except Exception as e:  # noqa: BLE001
            acc.connection_status, acc.last_error = "ERROR", str(e)[:500]
    elif (acc.config or {}).get("adapter") in ("gemini_omni", "veo_vertex", "gemini_tts", "gemini_llm"):
        # Đọc thông tin model — không tạo nội dung nên không phát sinh chi phí
        try:
            if acc.config["adapter"] in ("gemini_omni", "veo_vertex"):
                from app.providers.video.registry import build_real_provider

                build_real_provider(acc, key).test_connection()
            elif acc.config["adapter"] == "gemini_llm":
                from app.providers.llm.gemini_provider import GeminiLLMProvider

                GeminiLLMProvider(api_key=key, config=acc.config).test_connection()
            else:
                from app.providers.tts.gemini_tts import GeminiTTSProvider

                GeminiTTSProvider(api_key=key, config=acc.config).test_connection()
            acc.connection_status, acc.last_error, acc.last_verified_at = "VERIFIED", None, datetime.now(timezone.utc)
        except Exception as e:  # noqa: BLE001
            acc.connection_status, acc.last_error = "ERROR", str(e)[:500]
    else:
        acc.connection_status = "CONFIGURED_UNVERIFIED"
        acc.last_error = "Chưa có bài kiểm tra tự động cho nhà cung cấp này — cần xác minh thủ công với tài khoản thật"
    audit.record(ctx, "provider.test", "provider_account", acc.id, after={"status": acc.connection_status})
    ctx.db.commit()
    return acc


# ---------- Budget & cost ----------
@router.get("/budgets", response_model=list[BudgetOut])
def budgets(ctx: Ctx = Depends(require("cost.view"))):
    return ctx.db.scalars(select(BudgetLimit).where(BudgetLimit.data_mode == ctx.mode)).all()


@router.post("/budgets", response_model=BudgetOut, status_code=201)
def upsert_budget(data: BudgetIn, ctx: Ctx = Depends(require("admin.budget"))):
    if data.scope not in ("GLOBAL", "CHANNEL", "PROVIDER") or data.period not in ("DAILY", "MONTHLY"):
        raise ValidationFailed("Phạm vi/kỳ ngân sách không hợp lệ")
    b = ctx.db.scalar(select(BudgetLimit).where(BudgetLimit.scope == data.scope, BudgetLimit.scope_ref == data.scope_ref,
                                                BudgetLimit.period == data.period, BudgetLimit.data_mode == ctx.mode))
    before = {"limit": float(b.limit_amount)} if b else None
    if b is None:
        b = BudgetLimit(data_mode=ctx.mode, **data.model_dump())
        ctx.db.add(b)
    else:
        for k, v in data.model_dump().items():
            setattr(b, k, v)
    ctx.db.flush()
    audit.record(ctx, "budget.upsert", "budget_limit", b.id, before=before, after=data.model_dump(mode="json"))
    ctx.db.commit()
    return b


@router.delete("/budgets/{bid}")
def delete_budget(bid: uuid.UUID, ctx: Ctx = Depends(require("admin.budget"))):
    b = ctx.db.get(BudgetLimit, bid)
    if b is None or b.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy hạn mức")
    audit.record(ctx, "budget.delete", "budget_limit", b.id, before={"scope": b.scope, "limit": float(b.limit_amount)})
    ctx.db.delete(b)
    ctx.db.commit()
    return {"ok": True}


@router.get("/costs")
def costs(date_from: datetime | None = None, date_to: datetime | None = None, project_id: uuid.UUID | None = None,
          ctx: Ctx = Depends(require("cost.view"))):
    q = select(CostRecord).where(CostRecord.data_mode == ctx.mode)
    if date_from:
        q = q.where(CostRecord.created_at >= date_from)
    if date_to:
        q = q.where(CostRecord.created_at <= date_to)
    if project_id:
        q = q.where(CostRecord.project_id == project_id)
    rows = ctx.db.scalars(q.order_by(CostRecord.created_at.desc()).limit(500)).all()
    by_cat: dict = {}
    by_provider: dict = {}
    for r in rows:
        by_cat[r.category] = by_cat.get(r.category, 0) + float(r.amount)
        by_provider[r.provider_code] = by_provider.get(r.provider_code, 0) + float(r.amount)
    return {"total": sum(float(r.amount) for r in rows), "by_category": by_cat, "by_provider": by_provider,
            "simulated_total": sum(float(r.amount) for r in rows if r.is_simulated),
            "items": [{"id": str(r.id), "created_at": r.created_at.isoformat(), "category": r.category,
                       "provider_code": r.provider_code, "amount": float(r.amount), "is_simulated": r.is_simulated,
                       "project_id": str(r.project_id) if r.project_id else None, "description": r.description} for r in rows]}


# ---------- Settings & mode ----------
@router.get("/settings")
def settings(ctx: Ctx = Depends(require("admin.settings"))):
    return {k: service.get_setting(ctx.db, k) for k in service.DEFAULT_SETTINGS}


@router.put("/settings/{key}")
def set_setting(key: str, data: SettingIn, ctx: Ctx = Depends(require("admin.settings"))):
    if key == "qc.policy" and not (90 <= float(data.value.get("min_total", 98)) <= 100):
        raise ValidationFailed("Ngưỡng QC phải trong khoảng 90–100")
    v = service.set_setting(ctx, key, data.value)
    ctx.db.commit()
    return v


@router.post("/mode")
def set_mode(data: ModeIn, ctx: Ctx = Depends(require("admin.mode"))):
    m = service.set_mode(ctx, data.mode, data.confirm_text)
    ctx.db.commit()
    return {"mode": m}


# ---------- Audit & notifications ----------
@router.get("/audit-logs", response_model=Page[AuditOut])
def audit_logs(action: str | None = None, entity_type: str | None = None, actor_id: str | None = None,
               entity_id: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(100, le=500),
               ctx: Ctx = Depends(require("admin.audit"))):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.ilike(f"{action}%"))
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    total = ctx.db.scalar(select(func.count()).select_from(q.subquery()))
    items = ctx.db.scalars(q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(unread: bool = False, ctx: Ctx = Depends(require("dashboard.view"))):
    q = select(Notification).where(Notification.data_mode == ctx.mode,
                                   (Notification.user_id.is_(None)) | (Notification.user_id == ctx.actor.user_uuid))
    if unread:
        q = q.where(Notification.read_at.is_(None))
    return ctx.db.scalars(q.order_by(Notification.created_at.desc()).limit(100)).all()


@router.post("/notifications/read-all")
def read_all(ctx: Ctx = Depends(require("dashboard.view"))):
    for n in ctx.db.scalars(select(Notification).where(Notification.data_mode == ctx.mode, Notification.read_at.is_(None),
                                                       (Notification.user_id.is_(None)) | (Notification.user_id == ctx.actor.user_uuid))):
        n.read_at = datetime.now(timezone.utc)
    ctx.db.commit()
    return {"ok": True}


# ---------- Health & backup ----------
@router.get("/health")
def health(ctx: Ctx = Depends(require("admin.settings"))):
    from app.api.health import system_health
    from app.workflows.celery_client import worker_status

    data = system_health(ctx.db)
    data["mode"] = ctx.mode
    data["worker"] = worker_status()
    return data


@router.get("/backups")
def backups(ctx: Ctx = Depends(require("admin.backup"))):
    records = ctx.db.scalars(select(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(50)).all()
    return {"files": backup.list_files(),
            "records": [{"id": str(r.id), "file_name": r.file_name, "size_bytes": r.size_bytes, "status": r.status,
                         "checksum": r.checksum, "note": r.note, "created_at": r.created_at.isoformat(),
                         "restored_at": r.restored_at.isoformat() if r.restored_at else None} for r in records]}


@router.post("/backups", status_code=201)
def create_backup(data: BackupIn, ctx: Ctx = Depends(require("admin.backup"))):
    res = backup.create_backup(include_media=data.include_media)
    rec = BackupRecord(file_name=res["file_name"], size_bytes=res["size_bytes"], checksum=res["checksum"],
                       created_by=ctx.actor.user_uuid, note=data.note[:255])
    ctx.db.add(rec)
    audit.record(ctx, "backup.create", "backup", res["file_name"], after=res)
    ctx.db.commit()
    return res


@router.post("/backups/restore")
def restore(data: RestoreIn, ctx: Ctx = Depends(require("admin.backup"))):
    if ctx.actor.role_code != "SUPER_ADMIN":
        raise ValidationFailed("Chỉ Super Admin được khôi phục dữ liệu")
    if data.confirm_text != f"RESTORE {data.file_name}":
        raise ValidationFailed(f"Nhập chính xác 'RESTORE {data.file_name}' để xác nhận")
    backup.resolve_backup(data.file_name)
    actor = ctx.actor
    ctx.db.rollback()
    ctx.db.close()
    backup.restore_backup(data.file_name)
    from app.core.context import Ctx as C
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        c2 = C(db=db, actor=actor, mode=service.get_mode(db), ip=ctx.ip)
        audit.record(c2, "backup.restore", "backup", data.file_name)
        db.add(BackupRecord(file_name=data.file_name, status="RESTORED", restored_at=datetime.now(timezone.utc),
                            note=f"Khôi phục bởi {actor.label}"))
        db.commit()
    finally:
        db.close()
    return {"ok": True, "restored": data.file_name}
