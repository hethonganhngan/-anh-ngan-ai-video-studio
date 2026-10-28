"""Agent Registry & nhật ký thực thi (M14)."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin, utcnow


class AgentConfig(TimestampMixin, Base):
    __tablename__ = "agent_configs"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)  # A01..A10
    name: Mapped[str] = mapped_column(String(80))
    role_description: Mapped[str] = mapped_column(Text)
    provider_code: Mapped[str] = mapped_column(String(60), default="mock-llm")
    model: Mapped[str] = mapped_column(String(80), default="mock-deterministic-v1")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_actions: Mapped[list] = mapped_column(JSONB, default=list)
    prompt_template_code: Mapped[str | None] = mapped_column(String(80))
    max_runs_per_day: Mapped[int] = mapped_column(Integer, default=500)
    max_cost_per_run: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=20000)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4000)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=60)


class AgentExecution(UUIDMixin, DataModeMixin, Base):
    __tablename__ = "agent_executions"
    __table_args__ = (Index("ix_agent_exec_agent_time", "agent_code", "started_at"),)
    agent_code: Mapped[str] = mapped_column(String(10), ForeignKey("agent_configs.code"), index=True)
    action: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(80))
    provider_code: Mapped[str] = mapped_column(String(60))
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_versions.id", ondelete="SET NULL"))
    prompt_version_label: Mapped[str | None] = mapped_column(String(80))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    input_ref: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_ref: Mapped[dict] = mapped_column(JSONB, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")  # RUNNING | SUCCEEDED | FAILED | REJECTED
    error: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
