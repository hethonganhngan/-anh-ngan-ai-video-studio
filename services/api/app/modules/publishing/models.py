"""B10 — Publishing Manager: lịch nội dung, bài đăng (thủ công / API chính thức)."""
import uuid
from datetime import datetime

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class Publication(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "publications"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    render_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("renders.id", ondelete="SET NULL"))
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"), index=True)
    platform: Mapped[str] = mapped_column(String(20))  # FACEBOOK | TIKTOK | YOUTUBE | ZALO
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list] = mapped_column(JSONB, default=list)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post_url: Mapped[str | None] = mapped_column(String(500))
    publish_mode: Mapped[str] = mapped_column(String(10), default="MANUAL")  # MANUAL | API
    # DRAFT | SCHEDULED | PUBLISH_QUEUED | EXPORTED | PUBLISHED | FAILED | CANCELLED
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    export_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    published_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
