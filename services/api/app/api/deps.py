"""Dependency FastAPI: DB, người dùng hiện tại (cookie httpOnly hoặc Bearer), kiểm tra quyền, CSRF."""
import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.context import Actor, Ctx
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_token
from app.db.session import get_db
from app.modules.administration.models import User
from app.modules.administration.service import get_mode

ACCESS_COOKIE = "an_access"
CSRF_COOKIE = "an_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _token_from_request(request: Request) -> tuple[str | None, bool]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), False
    return request.cookies.get(ACCESS_COOKIE), True


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token, via_cookie = _token_from_request(request)
    if not token:
        raise Unauthorized("Chưa đăng nhập")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Phiên đăng nhập đã hết hạn", code="TOKEN_EXPIRED")
    except jwt.PyJWTError:
        raise Unauthorized("Token không hợp lệ")
    if via_cookie and request.method not in SAFE_METHODS:
        header = request.headers.get("x-csrf-token")
        cookie = request.cookies.get(CSRF_COOKIE)
        if not header or not cookie or header != cookie or payload.get("csrf") != cookie:
            raise Forbidden("CSRF token không hợp lệ", code="CSRF_FAILED")
    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (KeyError, ValueError):
        raise Unauthorized("Token không hợp lệ")
    if user is None or not user.is_active or user.deleted_at is not None:
        raise Unauthorized("Tài khoản không hoạt động")
    if payload.get("pwv") != user.password_hash[-12:]:
        raise Unauthorized("Phiên đăng nhập không còn hiệu lực", code="TOKEN_REVOKED")
    return user


def get_ctx(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ctx:
    actor = Actor(type="USER", id=str(user.id), label=user.full_name, permissions=user.permission_codes,
                  role_code=user.role.code)
    return Ctx(db=db, actor=actor, mode=get_mode(db), ip=request.client.host if request.client else None,
               user_agent=request.headers.get("user-agent"))


def require(*perms: str) -> Callable[..., Ctx]:
    def _dep(ctx: Ctx = Depends(get_ctx)) -> Ctx:
        for p in perms:
            ctx.require(p)
        return ctx

    return _dep
