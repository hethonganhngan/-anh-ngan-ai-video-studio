"""B11 — Analytics Engine: số liệu hiệu quả sau đăng (thủ công/CSV/API chính thức)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, DataModeMixin, TimestampMixin, UUIDMixin, utcnow


class AnalyticsSnapshot(UUIDMixin, TimestampMixin, DataModeMixin, Base):
    __tablename__ = "analytics_snapshots"
    publication_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    retention_rate: Mapped[float | None] = mapped_column(Float)  # % xem hết, nếu nền tảng cung cấp
    avg_watch_sec: Mapped[float | None] = mapped_column(Float)
    conversions: Mapped[int | None] = mapped_column(Integer)  # nếu có (tin nhắn, đơn hàng)
    source: Mapped[str] = mapped_column(String(10), default="MANUAL")  # MANUAL | CSV | API
    entered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
