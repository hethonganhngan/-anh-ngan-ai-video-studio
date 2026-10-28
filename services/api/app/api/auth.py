"""Xác thực: đăng nhập (rate limit + khoá tạm), đăng xuất, thông tin phiên, đổi mật khẩu."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.api.schemas import Email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ACCESS_COOKIE, CSRF_COOKIE, get_ctx, get_current_user
from app.core import audit
from app.core.config import get_settings
from app.core.context import Actor, Ctx
from app.core.errors import RateLimited, Unauthorized, ValidationFailed
from app.core.rate_limit import hit
from app.core.security import create_access_token, hash_password, validate_password_strength, verify_password
from app.db.session import get_db
from app.modules.administration.models import User
from app.modules.administration.service import get_mode

router = APIRouter(prefix="/auth", tags=["Auth"])
MAX_FAILED = 5
LOCK_MINUTES = 15


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


def user_payload(user: User, mode: str) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": {"code": user.role.code, "name": user.role.name},
        "permissions": sorted(user.permission_codes),
        "must_change_password": user.must_change_password,
        "is_demo": user.is_demo,
        "mode": mode,
    }


def _issue(response: Response, user: User) -> str:
    s = get_settings()
    csrf = secrets.token_urlsafe(24)
    token = create_access_token(str(user.id), {"csrf": csrf, "pwv": user.password_hash[-12:]})
    max_age = s.access_token_expire_minutes * 60
    response.set_cookie(ACCESS_COOKIE, token, httponly=True, secure=s.cookie_secure, samesite="lax", max_age=max_age, path="/")
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=s.cookie_secure, samesite="lax", max_age=max_age, path="/")
    return token


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    ip = request.client.host if request.client else "unknown"
    ok, _ = hit(f"login:{ip}:{data.email.lower()}", s.login_rate_limit_per_minute)
    if not ok:
        raise RateLimited("Quá nhiều lần đăng nhập. Vui lòng thử lại sau 1 phút.")
    user = db.scalar(select(User).where(User.email == data.email.lower(), User.deleted_at.is_(None)))
    mode = get_mode(db)
    now = datetime.now(timezone.utc)
    ctx = Ctx(db=db, actor=Actor(type="SYSTEM", id=None, label=data.email.lower()), mode=mode, ip=ip,
              user_agent=request.headers.get("user-agent"))
    if user and user.locked_until and user.locked_until > now:
        raise Unauthorized("Tài khoản tạm khoá do đăng nhập sai nhiều lần. Thử lại sau.", code="ACCOUNT_LOCKED")
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_login_count = 0
        audit.record(ctx, "auth.login_failed", "user", user.id if user else None)
        db.commit()
        raise Unauthorized("Email hoặc mật khẩu không đúng", code="INVALID_CREDENTIALS")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    ctx.actor = Actor(type="USER", id=str(user.id), label=user.full_name)
    audit.record(ctx, "auth.login", "user", user.id)
    db.commit()
    token = _issue(response, user)
    return {"user": user_payload(user, mode), "access_token": token, "token_type": "bearer"}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_payload(user, get_mode(db))


@router.post("/change-password")
def change_password(data: ChangePasswordIn, response: Response, ctx: Ctx = Depends(get_ctx)):
    user = ctx.db.get(User, ctx.actor.user_uuid)
    if not verify_password(data.current_password, user.password_hash):
        raise ValidationFailed("Mật khẩu hiện tại không đúng")
    issues = validate_password_strength(data.new_password)
    if issues:
        raise ValidationFailed("Mật khẩu chưa đủ mạnh", details=issues)
    if data.new_password == data.current_password:
        raise ValidationFailed("Mật khẩu mới phải khác mật khẩu cũ")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    audit.record(ctx, "auth.change_password", "user", user.id)
    ctx.db.commit()
    _issue(response, user)
    return {"ok": True}
