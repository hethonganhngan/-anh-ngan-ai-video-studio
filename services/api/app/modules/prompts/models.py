"""B04 — Prompt Engine: template prompt có phiên bản, kích hoạt tách theo chế độ DEMO/PRODUCTION."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PromptTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_templates"
    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    agent_code: Mapped[str] = mapped_column(String(10), index=True)
    purpose: Mapped[str] = mapped_column(Text, default="")
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"))
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL", use_alter=True)
    )
    demo_active_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL", use_alter=True)
    )


class PromptVersion(UUIDMixin, TimestampMixin, Base):
    """Phiên bản prompt — bất biến. Chỉ phiên bản APPROVED mới được kích hoạt."""

    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("template_id", "version_no", name="prompt_version_no"),)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompt_templates.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    rules: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT | APPROVED | RETIRED
    data_mode: Mapped[str] = mapped_column(String(16), default="PRODUCTION")
    change_note: Mapped[str] = mapped_column(String(255), default="")
    source_lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons_learned.id", ondelete="SET NULL", use_alter=True)
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
