"""B09 — AI Lessons Learned Engine: bài học đã kiểm chứng, áp dụng vào prompt chuẩn sau phê duyệt, có rollback."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin


class LessonLearned(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "lessons_learned"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    feedback_case_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("feedback_cases.id", ondelete="SET NULL"))
    # RESOLVED_ERROR | FAILED_PROMPT | EFFECTIVE_PROMPT | GOOD_VOICE_LOCK | GOOD_CHARACTER_LOCK | ROOT_CAUSE | EFFECTIVE_CAPA
    lesson_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(255))
    lesson: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text, default="")
    capa_summary: Mapped[str] = mapped_column(Text, default="")
    verification_summary: Mapped[str] = mapped_column(Text, default="")
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), index=True)
    character_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"), index=True)
    error_category: Mapped[str | None] = mapped_column(String(40), index=True)
    provider_code: Mapped[str | None] = mapped_column(String(60), index=True)
    prompt_example: Mapped[str] = mapped_column(Text, default="")
    # {template_code, append_negative, append_rule}
    proposed_change: Mapped[dict] = mapped_column(JSONB, default=dict)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    # DRAFT | PENDING_APPROVAL | APPROVED | APPLIED | ROLLED_BACK | REJECTED
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    history: Mapped[list] = mapped_column(JSONB, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_versions.id", ondelete="SET NULL"))
    previous_prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_versions.id", ondelete="SET NULL"))
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
