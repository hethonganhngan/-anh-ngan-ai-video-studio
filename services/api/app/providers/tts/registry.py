"""Chọn TTS Provider theo chế độ. DEMO: chỉ Mock (không gọi API tính phí). PRODUCTION: provider TTS đã bật + có key."""
from app.core.errors import ProviderUnavailable, ValidationFailed
from app.core.security import decrypt_secret
from app.modules.administration.models import ProviderAccount
from app.providers.tts.base import TTSProvider
from app.providers.tts.mock import MockTTSProvider
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_tts_provider(db: Session, code: str, mode: str) -> TTSProvider:
    if mode == "DEMO":
        return MockTTSProvider()
    if code in ("", "manual", "mock_tts"):
        raise ValidationFailed("Voice Profile chưa chọn giọng AI (provider) — vào M04 chọn Gemini TTS và tên giọng",
                               code="VOICE_NOT_AI")
    acc = db.scalar(select(ProviderAccount).where(ProviderAccount.provider_code == code,
                                                  ProviderAccount.provider_type == "TTS"))
    if acc is None:
        raise ValidationFailed(f"Nhà cung cấp giọng đọc '{code}' không tồn tại", code="UNKNOWN_PROVIDER")
    if not acc.is_enabled or not acc.secret_encrypted:
        raise ProviderUnavailable(f"{acc.name} chưa bật hoặc chưa có API key (M15 → API Connections)")
    if (acc.config or {}).get("adapter") == "gemini_tts":
        from app.providers.tts.gemini_tts import GeminiTTSProvider

        return GeminiTTSProvider(api_key=decrypt_secret(acc.secret_encrypted), config=acc.config,
                                 unit_cost_vnd_per_sec=acc.unit_cost)
    raise ValidationFailed(f"Chưa hỗ trợ adapter TTS cho '{code}'", code="UNSUPPORTED_PROVIDER")
