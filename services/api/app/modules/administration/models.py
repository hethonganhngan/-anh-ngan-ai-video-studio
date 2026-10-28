"""B12 — Administration & Cost Manager: người dùng, RBAC, audit, nhà cung cấp, ngân sách, chi phí."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Table, Text, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, DataModeMixin, SoftDeleteMixin, TimestampMixin, UUIDMixin, utcnow

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class Role(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(255), default="")
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[Role] = relationship(lazy="selectin")

    @property
    def permission_codes(self) -> set[str]:
        return {p.code for p in self.role.permissions} if self.role else set()


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_type: Mapped[str] = mapped_column(String(16), default="USER")  # USER | AGENT | SYSTEM
    actor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor_label: Mapped[str | None] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    data_mode: Mapped[str] = mapped_column(String(16), default="DEMO")


class SystemSetting(TimestampMixin, Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ProviderAccount(UUIDMixin, TimestampMixin, Base):
    """Kết nối API của nhà cung cấp. Secret được mã hoá, chỉ hiển thị 4 ký tự cuối."""

    __tablename__ = "provider_accounts"
    provider_type: Mapped[str] = mapped_column(String(20))  # VIDEO | LLM | TTS | PUBLISH | STORAGE
    provider_code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    secret_last4: Mapped[str | None] = mapped_column(String(8))
    # NOT_CONFIGURED | CONFIGURED_UNVERIFIED | VERIFIED | ERROR | BUILTIN
    connection_status: Mapped[str] = mapped_column(String(32), default="NOT_CONFIGURED")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)  # VND / đơn vị (giây video, 1K token...)
    cost_unit: Mapped[str] = mapped_column(String(30), default="SECOND")


class BudgetLimit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "budget_limits"
    __table_args__ = (UniqueConstraint("scope", "scope_ref", "period", "data_mode", name="budget_scope"),)
    scope: Mapped[str] = mapped_column(String(20))  # GLOBAL | CHANNEL | PROVIDER
    scope_ref: Mapped[str] = mapped_column(String(64), default="*")
    period: Mapped[str] = mapped_column(String(10), default="MONTHLY")  # DAILY | MONTHLY
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    alert_threshold_pct: Mapped[int] = mapped_column(Integer, default=80)
    hard_stop: Mapped[bool] = mapped_column(Boolean, default=True)
    data_mode: Mapped[str] = mapped_column(String(16), default="DEMO")


class CostRecord(UUIDMixin, DataModeMixin, Base):
    __tablename__ = "cost_records"
    __table_args__ = (Index("ix_cost_records_period", "data_mode", "created_at"),)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id", ondelete="SET NULL"), index=True)
    scene_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"))
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("generation_jobs.id", ondelete="SET NULL"))
    agent_execution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_executions.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(20))  # LLM | VIDEO_GEN | TTS | RENDER | STORAGE | OTHER
    provider_code: Mapped[str] = mapped_column(String(60))
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 4), default=0)
    unit: Mapped[str] = mapped_column(String(30), default="SECOND")
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))  # VND
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(10), default="INFO")  # INFO | WARNING | CRITICAL
    category: Mapped[str] = mapped_column(String(30), default="SYSTEM")
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(255))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_mode: Mapped[str] = mapped_column(String(16), default="DEMO")


class BackupRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "backups"
    file_name: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="CREATED")  # CREATED | FAILED | RESTORED
    checksum: Mapped[str | None] = mapped_column(String(80))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str] = mapped_column(String(255), default="")
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
