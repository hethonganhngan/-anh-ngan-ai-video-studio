"""B01 — Project Manager: kênh, Brand DNA, dự án video, lô sản xuất, nhật ký workflow."""
import uuid
from datetime import datetime
from decimal import Decimal

from app.db.base import Base, DataModeMixin, SoftDeleteMixin, TimestampMixin, UUIDMixin, utcnow
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Channel(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "channels"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    platforms: Mapped[list] = mapped_column(JSONB, default=list)  # ["FACEBOOK","TIKTOK","YOUTUBE","ZALO"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    brand_profile: Mapped["BrandProfile | None"] = relationship(back_populates="channel", uselist=False, lazy="selectin")


class BrandProfile(UUIDMixin, TimestampMixin, Base):
    """Brand DNA của kênh. Mỗi lần sửa tăng version và lưu bản cũ vào history."""

    __tablename__ = "brand_profiles"
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), unique=True)
    slogan: Mapped[str] = mapped_column(String(255), default="")
    brand_promise: Mapped[str] = mapped_column(String(255), default="")
    big_idea: Mapped[str] = mapped_column(String(255), default="")
    brand_voice: Mapped[list] = mapped_column(JSONB, default=list)
    audience: Mapped[str] = mapped_column(Text, default="")
    content_pillars: Mapped[list] = mapped_column(JSONB, default=list)
    character_set: Mapped[list] = mapped_column(JSONB, default=list)  # character codes
    voice_set: Mapped[list] = mapped_column(JSONB, default=list)
    scene_set: Mapped[list] = mapped_column(JSONB, default=list)
    cta_rules: Mapped[list] = mapped_column(JSONB, default=list)
    quality_rules: Mapped[list] = mapped_column(JSONB, default=list)
    publishing_rules: Mapped[list] = mapped_column(JSONB, default=list)
    forbidden_terms: Mapped[list] = mapped_column(JSONB, default=list)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    history: Mapped[list] = mapped_column(JSONB, default=list)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    channel: Mapped[Channel] = relationship(back_populates="brand_profile")


class ProductionBatch(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "production_batches"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"))
    title: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)


class Project(UUIDMixin, TimestampMixin, SoftDeleteMixin, DataModeMixin, Base):
    """Một dự án = một video. Trạng thái chạy theo state machine trong app.workflows."""

    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_mode_status", "data_mode", "status"),)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"), index=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("production_batches.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    topic: Mapped[str] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(Text, default="")
    duration_sec: Mapped[int] = mapped_column(Integer, default=32)
    aspect_ratio: Mapped[str] = mapped_column(String(8), default="9:16")
    style: Mapped[str] = mapped_column(String(160), default="")
    setting: Mapped[str] = mapped_column(String(255), default="")
    cta: Mapped[str] = mapped_column(String(255), default="")
    character_ids: Mapped[list] = mapped_column(JSONB, default=list)
    scene_lock_ids: Mapped[list] = mapped_column(JSONB, default=list)
    voice_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("voice_profiles.id", ondelete="SET NULL"))
    budget_limit: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    automation_level: Mapped[str] = mapped_column(String(12), default="ASSISTED")  # MANUAL | ASSISTED | AUTO
    video_provider_code: Mapped[str] = mapped_column(String(60), default="mock")
    status: Mapped[str] = mapped_column(String(32), default="CREATED", index=True)
    resume_status: Mapped[str | None] = mapped_column(String(32))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(8), default="NORMAL")
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    timeline: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel: Mapped[Channel] = relationship(lazy="selectin")


class WorkflowEvent(UUIDMixin, Base):
    __tablename__ = "workflow_events"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor_type: Mapped[str] = mapped_column(String(16))  # USER | AGENT | SYSTEM
    actor_ref: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
