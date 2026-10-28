"""B03 — Character & Voice Manager: nhân vật, ảnh tham chiếu, Character/Voice/Scene Lock bất biến."""
import uuid
from datetime import datetime

from app.db.base import Base, DataModeMixin, SoftDeleteMixin, TimestampMixin, UUIDMixin
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Character(UUIDMixin, TimestampMixin, SoftDeleteMixin, DataModeMixin, Base):
    __tablename__ = "characters"
    code: Mapped[str] = mapped_column(String(40), unique=True)  # Character ID, ví dụ CHR-ANNGAN-001
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    age_range: Mapped[str] = mapped_column(String(40), default="")
    gender: Mapped[str] = mapped_column(String(20), default="")
    appearance: Mapped[str] = mapped_column(Text, default="")
    outfit: Mapped[str] = mapped_column(Text, default="")
    expressions: Mapped[list] = mapped_column(JSONB, default=list)
    personality: Mapped[str] = mapped_column(Text, default="")
    voice_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("voice_profiles.id", ondelete="SET NULL"))
    active_lock_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("character_locks.id", ondelete="SET NULL", use_alter=True)
    )
    consent_status: Mapped[str] = mapped_column(String(20), default="NOT_REQUIRED")  # NOT_REQUIRED|PENDING|GRANTED|REVOKED
    usage_rights: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT | LOCKED | ARCHIVED
    references: Mapped[list["CharacterReference"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class CharacterReference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "character_references"
    __table_args__ = (UniqueConstraint("character_id", "ref_type", "version_no", name="char_ref_version"),)
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    ref_type: Mapped[str] = mapped_column(String(20))  # FRONT | THREE_QUARTER | FULL_BODY | EXPRESSION | OUTFIT
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id"))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str] = mapped_column(String(255), default="")


class CharacterLock(UUIDMixin, TimestampMixin, Base):
    """Bản khoá nhân vật. Khi APPROVED thì lock_data bất biến (trigger DB + service)."""

    __tablename__ = "character_locks"
    __table_args__ = (UniqueConstraint("character_id", "version_no", name="char_lock_version"),)
    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    lock_data: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT | APPROVED | RETIRED
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_note: Mapped[str] = mapped_column(String(255), default="")


class VoiceProfile(UUIDMixin, TimestampMixin, SoftDeleteMixin, DataModeMixin, Base):
    __tablename__ = "voice_profiles"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    accent: Mapped[str] = mapped_column(String(60), default="Miền Trung")
    gender: Mapped[str] = mapped_column(String(20), default="")
    age_range: Mapped[str] = mapped_column(String(40), default="")
    tone: Mapped[str] = mapped_column(String(160), default="")
    speaking_rate: Mapped[str] = mapped_column(String(40), default="vừa phải")
    provider_code: Mapped[str] = mapped_column(String(60), default="manual")
    provider_voice_id: Mapped[str | None] = mapped_column(String(120))
    audio_reference_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    consent_status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING | GRANTED | REVOKED
    consent_document_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    usage_rights: Mapped[str] = mapped_column(Text, default="")
    rights_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_lock_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("voice_locks.id", ondelete="SET NULL", use_alter=True)
    )
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")


class VoiceLock(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "voice_locks"
    __table_args__ = (UniqueConstraint("voice_profile_id", "version_no", name="voice_lock_version"),)
    voice_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("voice_profiles.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    lock_data: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_note: Mapped[str] = mapped_column(String(255), default="")


class SceneLock(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    """Khoá bối cảnh (Scene Lock). Mỗi bản ghi là một phiên bản; APPROVED thì bất biến."""

    __tablename__ = "scene_locks"
    __table_args__ = (UniqueConstraint("code", "version_no", name="scene_lock_version"),)
    code: Mapped[str] = mapped_column(String(40), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    lock_data: Mapped[dict] = mapped_column(JSONB)  # setting, lighting, props, colors, reference_asset_ids
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
