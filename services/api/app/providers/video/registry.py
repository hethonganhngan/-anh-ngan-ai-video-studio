"""Chọn Video Provider theo chế độ. DEMO: chỉ mock + manual_flow (không gọi API tính phí).
PRODUCTION: manual_flow + provider REAL_API đã bật và có key; KHÔNG cho dùng mock."""
from app.core.errors import ProviderUnavailable, ValidationFailed
from app.core.security import decrypt_secret
from app.modules.administration.models import ProviderAccount
from app.providers.video.base import VideoProvider
from app.providers.video.manual_flow import ManualFlowProvider
from app.providers.video.mock import MockVideoProvider
from app.providers.video.real_api import RealAPIProvider
from sqlalchemy import select
from sqlalchemy.orm import Session

BUILTIN = {"mock": MockVideoProvider, "manual_flow": ManualFlowProvider}


def get_video_provider(db: Session, code: str, mode: str) -> VideoProvider:
    if code == "mock":
        if mode != "DEMO":
            raise ValidationFailed("Mock Provider chỉ dùng trong DEMO MODE", code="MOCK_NOT_ALLOWED_IN_PRODUCTION")
        return MockVideoProvider()
    if code == "manual_flow":
        return ManualFlowProvider()
    acc = db.scalar(select(ProviderAccount).where(ProviderAccount.provider_code == code,
                                                  ProviderAccount.provider_type == "VIDEO"))
    if acc is None:
        raise ValidationFailed(f"Nhà cung cấp video '{code}' không tồn tại", code="UNKNOWN_PROVIDER")
    if mode == "DEMO":
        raise ValidationFailed("DEMO MODE không gọi API video tính phí", code="REAL_PROVIDER_BLOCKED_IN_DEMO")
    if not acc.is_enabled:
        raise ProviderUnavailable(f"Nhà cung cấp {acc.name} đang tắt")
    key = decrypt_secret(acc.secret_encrypted) if acc.secret_encrypted else None
    return RealAPIProvider(code=acc.provider_code, name=acc.name, api_key=key, config=acc.config)


def list_video_providers(db: Session, mode: str) -> list[dict]:
    out = []
    for cls in (MockVideoProvider, ManualFlowProvider):
        info = cls().info()
        info["available"] = not (cls is MockVideoProvider and mode != "DEMO")
        info["connection_status"] = "BUILTIN"
        out.append(info)
    for acc in db.scalars(select(ProviderAccount).where(ProviderAccount.provider_type == "VIDEO")).all():
        if acc.provider_code in BUILTIN:
            continue
        out.append({"code": acc.provider_code, "name": acc.name, "kind": "REAL_API", "is_real": True,
                    "available": mode == "PRODUCTION" and acc.is_enabled and bool(acc.secret_encrypted),
                    "connection_status": acc.connection_status, "unit_cost_vnd_per_sec": float(acc.unit_cost),
                    "max_duration_sec": acc.config.get("max_duration_sec", 8)})
    return out
