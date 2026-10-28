"""Service B12: cài đặt hệ thống, chế độ DEMO/PRODUCTION, ngân sách, chi phí, thông báo, người dùng."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core import audit
from app.core.context import Ctx
from app.core.errors import BudgetExceeded, Conflict, NotFound, ValidationFailed
from app.core.security import hash_password, validate_password_strength
from app.modules.administration.models import (
    BudgetLimit,
    CostRecord,
    Notification,
    Role,
    SystemSetting,
    User,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_SETTINGS: dict[str, dict] = {
    "system.mode": {"value": "DEMO"},
    "qc.policy": {"min_total": 98, "require_human_review": True, "blocking_severities": ["CRITICAL", "MAJOR"]},
    "generation.policy": {"max_retries": 3, "scene_seconds": 8, "aspect_ratio": "9:16", "max_dialogue_lines": 2},
    "notifications": {"budget_alert": True, "qc_failed": True, "feedback_p0": True, "email_enabled": False},
    "organization": {"name": "Hệ thống Sữa Ánh Ngân", "currency": "VND", "timezone": "Asia/Ho_Chi_Minh"},
}


# ---------- Cài đặt ----------
def get_setting(db: Session, key: str) -> dict:
    row = db.get(SystemSetting, key)
    if row is None:
        return dict(DEFAULT_SETTINGS.get(key, {}))
    merged = dict(DEFAULT_SETTINGS.get(key, {}))
    merged.update(row.value or {})
    return merged


def set_setting(ctx: Ctx, key: str, value: dict) -> dict:
    ctx.require("admin.settings")
    if key not in DEFAULT_SETTINGS:
        raise ValidationFailed(f"Khoá cài đặt không hợp lệ: {key}")
    if key == "system.mode":
        raise ValidationFailed("Dùng API chuyển chế độ riêng (admin.mode)")
    row = ctx.db.get(SystemSetting, key)
    before = row.value if row else None
    if row is None:
        row = SystemSetting(key=key, value=value, updated_by=ctx.actor.user_uuid)
        ctx.db.add(row)
    else:
        row.value = {**(row.value or {}), **value}
        row.updated_by = ctx.actor.user_uuid
    audit.record(ctx, "setting.update", "system_setting", key, before=before, after=row.value)
    return get_setting(ctx.db, key)


def get_mode(db: Session) -> str:
    return get_setting(db, "system.mode").get("value", "DEMO")


def set_mode(ctx: Ctx, mode: str, confirm_text: str) -> str:
    ctx.require("admin.mode")
    if mode not in ("DEMO", "PRODUCTION"):
        raise ValidationFailed("Chế độ phải là DEMO hoặc PRODUCTION")
    if confirm_text != mode:
        raise ValidationFailed(f"Nhập chính xác '{mode}' để xác nhận chuyển chế độ")
    row = ctx.db.get(SystemSetting, "system.mode")
    before = row.value if row else {"value": "DEMO"}
    if row is None:
        ctx.db.add(SystemSetting(key="system.mode", value={"value": mode}, updated_by=ctx.actor.user_uuid))
    else:
        row.value = {"value": mode}
        row.updated_by = ctx.actor.user_uuid
    audit.record(ctx, "system.mode_change", "system_setting", "system.mode", before=before, after={"value": mode})
    return mode


# ---------- Thông báo ----------
def notify(db: Session, mode: str, title: str, message: str, level: str = "INFO", category: str = "SYSTEM",
           link: str | None = None, user_id: uuid.UUID | None = None, dedupe_hours: int = 0) -> Notification | None:
    if dedupe_hours:
        since = datetime.now(timezone.utc) - timedelta(hours=dedupe_hours)
        exists = db.scalar(
            select(Notification.id).where(Notification.title == title, Notification.created_at >= since,
                                          Notification.data_mode == mode).limit(1)
        )
        if exists:
            return None
    n = Notification(title=title, message=message, level=level, category=category, link=link, user_id=user_id, data_mode=mode)
    db.add(n)
    return n


# ---------- Chi phí & ngân sách ----------
def _period_start(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "DAILY":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def spent(db: Session, mode: str, *, since: datetime | None = None, project_id=None, channel_id=None,
          provider_code: str | None = None) -> Decimal:
    q = select(func.coalesce(func.sum(CostRecord.amount), 0)).where(CostRecord.data_mode == mode)
    if since:
        q = q.where(CostRecord.created_at >= since)
    if project_id:
        q = q.where(CostRecord.project_id == project_id)
    if channel_id:
        q = q.where(CostRecord.channel_id == channel_id)
    if provider_code:
        q = q.where(CostRecord.provider_code == provider_code)
    return Decimal(db.scalar(q) or 0)


def check_budget(ctx: Ctx, *, estimated: Decimal, project=None, provider_code: str | None = None,
                 raise_on_exceed: bool = True) -> dict:
    """Kiểm tra trước khi phát sinh chi phí. Vượt hạn mức hard_stop → BudgetExceeded (không gọi API)."""
    db, mode = ctx.db, ctx.mode
    estimated = Decimal(estimated or 0)
    checks: list[dict] = []
    if project is not None and project.budget_limit and Decimal(project.budget_limit) > 0:
        used = spent(db, mode, project_id=project.id)
        checks.append({"scope": "PROJECT", "ref": project.code, "limit": Decimal(project.budget_limit), "used": used,
                       "hard_stop": True, "alert_pct": 80})
    limits = db.scalars(select(BudgetLimit).where(BudgetLimit.data_mode == mode)).all()
    for lim in limits:
        since = _period_start(lim.period)
        if lim.scope == "GLOBAL":
            used = spent(db, mode, since=since)
        elif lim.scope == "CHANNEL" and project is not None and str(project.channel_id) == lim.scope_ref:
            used = spent(db, mode, since=since, channel_id=project.channel_id)
        elif lim.scope == "PROVIDER" and provider_code and provider_code == lim.scope_ref:
            used = spent(db, mode, since=since, provider_code=provider_code)
        else:
            continue
        checks.append({"scope": lim.scope, "ref": lim.scope_ref, "period": lim.period, "limit": Decimal(lim.limit_amount),
                       "used": used, "hard_stop": lim.hard_stop, "alert_pct": lim.alert_threshold_pct})
    exceeded = []
    for c in checks:
        after = c["used"] + estimated
        c["after"] = after
        c["pct_after"] = float(after / c["limit"] * 100) if c["limit"] > 0 else 0.0
        if c["limit"] > 0 and after > c["limit"]:
            exceeded.append(c)
        elif c["pct_after"] >= c["alert_pct"]:
            notify(db, mode, f"Cảnh báo ngân sách {c['scope']} {c['ref']}",
                   f"Đã dùng {c['pct_after']:.0f}% hạn mức ({c['after']:,.0f}/{c['limit']:,.0f} VND)",
                   level="WARNING", category="BUDGET", dedupe_hours=12)
    blocking = [c for c in exceeded if c["hard_stop"]]
    result = {"estimated": estimated, "checks": checks, "exceeded": exceeded, "allowed": not blocking}
    if blocking:
        c = blocking[0]
        notify(db, mode, f"Chặn chi phí: vượt ngân sách {c['scope']} {c['ref']}",
               f"Ước tính {estimated:,.0f} VND làm vượt hạn mức {c['limit']:,.0f} VND", level="CRITICAL",
               category="BUDGET", dedupe_hours=1)
        if raise_on_exceed:
            raise BudgetExceeded(
                f"Vượt ngân sách {c['scope']} ({c['ref']}): đã dùng {c['used']:,.0f} + ước tính {estimated:,.0f} > hạn mức {c['limit']:,.0f} VND",
                details={"scope": c["scope"], "ref": c["ref"], "limit": float(c["limit"]), "used": float(c["used"]),
                         "estimated": float(estimated)},
            )
    return result


def record_cost(db: Session, mode: str, *, category: str, provider_code: str, amount: Decimal, quantity: Decimal = Decimal(0),
                unit: str = "SECOND", project=None, scene_id=None, generation_job_id=None, agent_execution_id=None,
                is_simulated: bool = True, description: str = "") -> CostRecord:
    rec = CostRecord(
        data_mode=mode, category=category, provider_code=provider_code, amount=Decimal(amount), quantity=Decimal(quantity),
        unit=unit, project_id=project.id if project is not None else None,
        channel_id=project.channel_id if project is not None else None, scene_id=scene_id,
        generation_job_id=generation_job_id, agent_execution_id=agent_execution_id, is_simulated=is_simulated,
        description=description[:255],
    )
    db.add(rec)
    return rec


# ---------- Người dùng ----------
def create_user(ctx: Ctx, *, email: str, full_name: str, role_code: str, password: str, must_change_password: bool = True) -> User:
    ctx.require("admin.users")
    email = email.lower().strip()
    if ctx.db.scalar(select(User.id).where(User.email == email)):
        raise Conflict("Email đã tồn tại")
    role = ctx.db.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise NotFound("Vai trò không tồn tại")
    if role.code == "SUPER_ADMIN" and ctx.actor.role_code != "SUPER_ADMIN":
        raise ValidationFailed("Chỉ Super Admin được tạo Super Admin")
    issues = validate_password_strength(password)
    if issues:
        raise ValidationFailed("Mật khẩu chưa đủ mạnh", details=issues)
    user = User(email=email, full_name=full_name, role_id=role.id, password_hash=hash_password(password),
                must_change_password=must_change_password)
    ctx.db.add(user)
    ctx.db.flush()
    audit.record(ctx, "user.create", "user", user.id, after={"email": email, "role": role_code})
    return user


def update_user(ctx: Ctx, user_id: uuid.UUID, *, full_name: str | None = None, role_code: str | None = None,
                is_active: bool | None = None) -> User:
    ctx.require("admin.users")
    user = ctx.db.get(User, user_id)
    if user is None or user.deleted_at:
        raise NotFound("Không tìm thấy người dùng")
    before = {"full_name": user.full_name, "role": user.role.code, "is_active": user.is_active}
    if str(user.id) == ctx.actor.id and (is_active is False or (role_code and role_code != user.role.code)):
        raise ValidationFailed("Không thể tự khoá hoặc tự đổi vai trò của chính mình")
    if full_name is not None:
        user.full_name = full_name
    if role_code is not None:
        role = ctx.db.scalar(select(Role).where(Role.code == role_code))
        if role is None:
            raise NotFound("Vai trò không tồn tại")
        if (role.code == "SUPER_ADMIN" or user.role.code == "SUPER_ADMIN") and ctx.actor.role_code != "SUPER_ADMIN":
            raise ValidationFailed("Chỉ Super Admin được thay đổi vai trò Super Admin")
        user.role_id = role.id
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    audit.record(ctx, "user.update", "user", user.id, before=before,
                 after={"full_name": user.full_name, "role": user.role.code, "is_active": user.is_active})
    return user
