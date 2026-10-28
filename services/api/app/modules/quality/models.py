"""B07 — Quality Control Engine: 10 tiêu chí x 10 điểm, phát hiện lỗi, phê duyệt."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin


class QCReview(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "qc_reviews"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    render_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("renders.id", ondelete="SET NULL"))
    scene_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"))
    review_type: Mapped[str] = mapped_column(String(10))  # SCENE | FINAL
    reviewer_type: Mapped[str] = mapped_column(String(10))  # AGENT | HUMAN
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    scores: Mapped[dict] = mapped_column(JSONB, default=dict)  # {criterion: {score, method, note}}
    total_score: Mapped[float] = mapped_column(Float, default=0)
    pending_manual: Mapped[list] = mapped_column(JSONB, default=list)
    automated_checks: Mapped[dict] = mapped_column(JSONB, default=dict)
    has_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[str] = mapped_column(String(20), default="PENDING")  # PASS | FAIL | NEEDS_MANUAL | PENDING
    notes: Mapped[str] = mapped_column(Text, default="")
    agent_execution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_executions.id", ondelete="SET NULL"))
    findings: Mapped[list["QCFinding"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class QCFinding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "qc_findings"
    qc_review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("qc_reviews.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"))
    criterion: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))  # CRITICAL | MAJOR | MINOR
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="OPEN")  # OPEN | RESOLVED | WAIVED
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    feedback_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feedback_cases.id", ondelete="SET NULL", use_alter=True)
    )


class Approval(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "approvals"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    render_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("renders.id", ondelete="SET NULL"))
    qc_review_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("qc_reviews.id", ondelete="SET NULL"))
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(10))  # APPROVED | REJECTED
    comment: Mapped[str] = mapped_column(Text, default="")
