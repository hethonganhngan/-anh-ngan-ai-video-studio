"""Thư viện tài nguyên (M12). File media ở Object Storage, DB chỉ lưu metadata + storage_key."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, DataModeMixin, SoftDeleteMixin, TimestampMixin, UUIDMixin


class Asset(UUIDMixin, TimestampMixin, SoftDeleteMixin, DataModeMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (Index("ix_assets_mode_type", "data_mode", "asset_type"),)
    # IMAGE | VIDEO | AUDIO | LOGO | CHARACTER | BACKGROUND | PRODUCT | TEMPLATE | REFERENCE | SUBTITLE | DOCUMENT
    asset_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    storage_backend: Mapped[str] = mapped_column(String(10), default="local")
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    duration_sec: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    media_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    usage_rights: Mapped[str] = mapped_column(String(30), default="UNKNOWN")  # OWNED|LICENSED|CONSENTED|AI_GENERATED|UNKNOWN
    rights_note: Mapped[str] = mapped_column(Text, default="")
    rights_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(30), default="UPLOAD")  # UPLOAD|MOCK_PROVIDER|MANUAL_FLOW|API_PROVIDER|RENDER
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    scene_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), index=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
