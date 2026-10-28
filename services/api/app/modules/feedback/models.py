"""B08 — Feedback Loop Engine 360°: INTAKE → VALIDATE → TRIAGE → ROOT CAUSE → CAPA → ASSIGN → VERIFY → STANDARDIZE."""
import uuid
from datetime import datetime

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin, utcnow
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


class FeedbackCase(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "feedback_cases"
    __table_args__ = (Index("ix_feedback_mode_status", "data_mode", "status"),)
    code: Mapped[str] = mapped_column(String(40), unique=True)  # Feedback ID
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    scene_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"))
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"))
    character_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("characters.id", ondelete="SET NULL"))
    provider_code: Mapped[str | None] = mapped_column(String(60))
    qc_finding_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("qc_findings.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(20))  # QC | CUSTOMER | INTERNAL | ANALYTICS | AGENT | PUBLISHING
    category: Mapped[str] = mapped_column(String(40), default="OTHER")  # loại lỗi
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[list] = mapped_column(JSONB, default=list)  # [{type, ref, note}]
    evidence_class: Mapped[str] = mapped_column(String(12), default="UNKNOWN")  # FACT | HYPOTHESIS | UNKNOWN
    priority: Mapped[str | None] = mapped_column(String(4))  # P0..P3
    status: Mapped[str] = mapped_column(String(20), default="NEW", index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kpi_name: Mapped[str | None] = mapped_column(String(120))
    kpi_before: Mapped[float | None] = mapped_column(Float)
    kpi_after: Mapped[float | None] = mapped_column(Float)
    kpi_target: Mapped[float | None] = mapped_column(Float)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reported_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    standardization_note: Mapped[str] = mapped_column(Text, default="")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events: Mapped[list["FeedbackEvent"]] = relationship(
        lazy="selectin", order_by="FeedbackEvent.created_at", cascade="all, delete-orphan"
    )


class FeedbackEvent(UUIDMixin, Base):
    __tablename__ = "feedback_events"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    feedback_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feedback_cases.id", ondelete="CASCADE"), index=True)
    step: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_type: Mapped[str] = mapped_column(String(10), default="USER")
    actor_ref: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text, default="")


class RootCauseAnalysis(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "root_cause_analyses"
    feedback_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feedback_cases.id", ondelete="CASCADE"), index=True)
    whys: Mapped[list] = mapped_column(JSONB, default=list)  # 5 Whys [{question, answer}]
    root_cause: Mapped[str] = mapped_column(Text)
    cause_category: Mapped[str] = mapped_column(String(40), default="OTHER")  # PROMPT|CHARACTER|VOICE|PROVIDER|SCRIPT|PROCESS|ASSET|OTHER
    evidence_class: Mapped[str] = mapped_column(String(12), default="HYPOTHESIS")
    confidence_pct: Mapped[int] = mapped_column(Integer, default=50)
    created_by_type: Mapped[str] = mapped_column(String(10), default="USER")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)


class CAPAAction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "capa_actions"
    feedback_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feedback_cases.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(12))  # CORRECTIVE | PREVENTIVE
    description: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="PROPOSED")  # PROPOSED|APPROVED|IN_PROGRESS|DONE|CANCELLED
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_evidence: Mapped[list] = mapped_column(JSONB, default=list)


class VerificationResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "verification_results"
    feedback_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feedback_cases.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(Text)
    kpi_before: Mapped[float | None] = mapped_column(Float)
    kpi_after: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
