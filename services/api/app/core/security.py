"""Băm mật khẩu (Argon2), JWT, mã hoá secret nhà cung cấp (Fernet)."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_ph = PasswordHasher()
JWT_ALG = "HS256"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> list[str]:
    issues = []
    if len(password) < 10:
        issues.append("Tối thiểu 10 ký tự")
    if not any(c.isupper() for c in password):
        issues.append("Cần ít nhất 1 chữ hoa")
    if not any(c.islower() for c in password):
        issues.append("Cần ít nhất 1 chữ thường")
    if not any(c.isdigit() for c in password):
        issues.append("Cần ít nhất 1 chữ số")
    return issues


def generate_password() -> str:
    return secrets.token_urlsafe(12) + "Aa1"


def create_access_token(user_id: str, extra: dict | None = None) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=s.access_token_expire_minutes), "typ": "access"}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.secret_key, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().secret_key, algorithms=[JWT_ALG])


def _fernet() -> Fernet:
    s = get_settings()
    key = s.encryption_key
    if not key:
        # Dẫn xuất từ SECRET_KEY khi chưa cấu hình riêng (dev). Production phải đặt ENCRYPTION_KEY.
        key = base64.urlsafe_b64encode(hashlib.sha256(s.secret_key.encode()).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def mask_secret(value: str) -> str:
    return value[-4:] if len(value) >= 8 else "****"
