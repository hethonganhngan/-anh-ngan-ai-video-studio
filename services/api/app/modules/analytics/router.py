"""B11 API — Analytics & Dashboard CEO (M01, M10)."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import require
from app.api.schemas import ORM
from app.core.context import Ctx
from app.core.errors import ValidationFailed
from app.modules.analytics import service
from app.modules.analytics.models import AnalyticsSnapshot

router = APIRouter(tags=["B11 Analytics Engine"])


class SnapshotIn(BaseModel):
    captured_at: datetime | None = None
    views: int = Field(ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    retention_rate: float | None = Field(default=None, ge=0, le=100)
    avg_watch_sec: float | None = Field(default=None, ge=0)
    conversions: int | None = Field(default=None, ge=0)


class SnapshotOut(ORM):
    id: uuid.UUID
    publication_id: uuid.UUID
    captured_at: datetime
    views: int
    likes: int
    comments: int
    shares: int
    saves: int
    retention_rate: float | None
    avg_watch_sec: float | None
    conversions: int | None
    source: str


@router.get("/dashboard")
def dashboard(channel_id: uuid.UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
              project_id: uuid.UUID | None = None, owner_id: uuid.UUID | None = None,
              ctx: Ctx = Depends(require("dashboard.view"))):
    return service.dashboard(ctx, channel_id=channel_id, date_from=date_from, date_to=date_to, project_id=project_id,
                             owner_id=owner_id)


@router.get("/analytics/performance")
def performance(channel_id: uuid.UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                ctx: Ctx = Depends(require("analytics.view"))):
    return service.performance(ctx, channel_id=channel_id, date_from=date_from, date_to=date_to)


@router.get("/analytics/insights")
def insights(channel_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("analytics.view"))):
    res = service.insights(ctx, channel_id)
    ctx.db.commit()
    return res


@router.get("/analytics/export.csv")
def export_csv(channel_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("analytics.view"))):
    return Response(service.export_csv(ctx, channel_id=channel_id), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="anngan_analytics.csv"'})


@router.get("/publications/{pid}/snapshots", response_model=list[SnapshotOut])
def snapshots(pid: uuid.UUID, ctx: Ctx = Depends(require("analytics.view"))):
    from sqlalchemy import select

    from app.modules.publishing.service import get_pub

    get_pub(ctx, pid)
    return ctx.db.scalars(select(AnalyticsSnapshot).where(AnalyticsSnapshot.publication_id == pid)
                          .order_by(AnalyticsSnapshot.captured_at)).all()


@router.post("/publications/{pid}/snapshots", response_model=SnapshotOut, status_code=201)
def add_snapshot(pid: uuid.UUID, data: SnapshotIn, ctx: Ctx = Depends(require("analytics.enter"))):
    s = service.add_snapshot(ctx, pid, data.model_dump())
    ctx.db.commit()
    return s


@router.post("/analytics/import")
async def import_csv(file: UploadFile = File(...), ctx: Ctx = Depends(require("analytics.enter"))):
    content = await file.read(5_000_001)
    if len(content) > 5_000_000:
        raise ValidationFailed("CSV tối đa 5MB")
    res = service.import_csv(ctx, content)
    ctx.db.commit()
    return res
