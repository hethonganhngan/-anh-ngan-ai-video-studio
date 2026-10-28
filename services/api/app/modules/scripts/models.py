"""B02 — AI Script Engine: ý tưởng, kịch bản có phiên bản, cảnh, phiên bản cảnh."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin


class Script(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "scripts"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    ideas: Mapped[list] = mapped_column(JSONB, default=list)  # [{title, angle, hook, score, scores{...}}]
    selected_idea_index: Mapped[int | None] = mapped_column(Integer)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("script_versions.id", ondelete="SET NULL", use_alter=True)
    )
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT | IN_REVIEW | APPROVED
    approved_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("script_versions.id", ondelete="SET NULL", use_alter=True)
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScriptVersion(UUIDMixin, TimestampMixin, Base):
    """Phiên bản kịch bản — bất biến sau khi tạo."""

    __tablename__ = "script_versions"
    __table_args__ = (UniqueConstraint("script_id", "version_no", name="script_version_no"),)
    script_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scripts.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255), default="")
    hook: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    cta: Mapped[str] = mapped_column(String(255), default="")
    scenes: Mapped[list] = mapped_column(JSONB, default=list)  # snapshot storyboard
    source: Mapped[str] = mapped_column(String(10), default="AGENT")  # AGENT | HUMAN
    change_note: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    agent_execution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_executions.id", ondelete="SET NULL"))


class Scene(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "scenes"
    __table_args__ = (UniqueConstraint("project_id", "order_index", name="scene_order"),)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255), default="")
    scene_type: Mapped[str] = mapped_column(String(60), default="")
    duration_sec: Mapped[int] = mapped_column(Integer, default=8)
    action: Mapped[str] = mapped_column(Text, default="")
    dialogue: Mapped[list] = mapped_column(JSONB, default=list)  # [{speaker, text}] tối đa 2
    setting: Mapped[str] = mapped_column(Text, default="")
    camera: Mapped[str] = mapped_column(String(255), default="")
    lighting: Mapped[str] = mapped_column(String(255), default="")
    sound: Mapped[str] = mapped_column(String(255), default="")
    character_ids: Mapped[list] = mapped_column(JSONB, default=list)
    scene_lock_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scene_locks.id", ondelete="SET NULL"))
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    prompt_parts: Mapped[dict] = mapped_column(JSONB, default=dict)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prompt_versions.id", ondelete="SET NULL"))
    current_version_no: Mapped[int] = mapped_column(Integer, default=1)
    # PLANNED | PROMPT_READY | GENERATING | GENERATED | QC_PASSED | QC_FAILED | NEEDS_MANUAL
    status: Mapped[str] = mapped_column(String(20), default="PLANNED")
    selected_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    versions: Mapped[list["SceneVersion"]] = relationship(
        back_populates="scene", order_by="SceneVersion.version_no", lazy="selectin", cascade="all, delete-orphan"
    )


class SceneVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scene_versions"
    __table_args__ = (UniqueConstraint("scene_id", "version_no", name="scene_version_no"),)
    scene_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    change_note: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    scene: Mapped[Scene] = relationship(back_populates="versions")
