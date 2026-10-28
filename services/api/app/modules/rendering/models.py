"""B06 — Render Engine: tác vụ dựng FFmpeg và bản render MP4."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin


class RenderJob(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "render_jobs"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)  # QUEUED|RUNNING|SUCCEEDED|FAILED|CANCELLED
    timeline: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(160))
    error_message: Mapped[str | None] = mapped_column(Text)
    log: Mapped[list] = mapped_column(JSONB, default=list)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Render(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "renders"
    __table_args__ = (UniqueConstraint("project_id", "version_no", name="render_version_no"),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    render_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("render_jobs.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    video_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id"))
    thumbnail_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"))
    subtitle_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"))
    duration_sec: Mapped[float] = mapped_column(Float, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    probe: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="READY")  # READY | QC_PASSED | QC_FAILED | APPROVED
    notes: Mapped[str] = mapped_column(Text, default="")
