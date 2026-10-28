"""B05 — Video Generation Manager: tác vụ tạo cảnh qua Provider Adapter."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin


class GenerationJob(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (Index("ix_generation_jobs_mode_status", "data_mode", "status"),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    scene_version_no: Mapped[int] = mapped_column(Integer, default=1)
    provider_code: Mapped[str] = mapped_column(String(60))
    # QUEUED | SUBMITTED | RUNNING | SUCCEEDED | FAILED | CANCELLED | NEEDS_MANUAL_ACTION | RETRY_PENDING | BLOCKED_BUDGET
    status: Mapped[str] = mapped_column(String(24), default="QUEUED", index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    provider_job_id: Mapped[str | None] = mapped_column(String(160))
    prompt_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    actual_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    result_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(160))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    log: Mapped[list] = mapped_column(JSONB, default=list)
