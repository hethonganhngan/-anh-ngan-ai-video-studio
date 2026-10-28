"""B10 API — Publishing (M10)."""
import uuid
from datetime import datetime

from app.api.deps import require
from app.api.schemas import ORM
from app.core.context import Ctx
from app.modules.projects.schemas import ProjectOut
from app.modules.publishing import service
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

router = APIRouter(prefix="/publications", tags=["B10 Publishing Manager"])


class PubIn(BaseModel):
    project_id: uuid.UUID
    platform: str
    caption: str = Field(default="", max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    scheduled_at: datetime | None = None
    publish_mode: str = "MANUAL"


class PubPatch(BaseModel):
    caption: str | None = None
    hashtags: list[str] | None = None
    scheduled_at: datetime | None = None


class PubOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    render_id: uuid.UUID | None
    channel_id: uuid.UUID
    platform: str
    caption: str
    hashtags: list
    scheduled_at: datetime | None
    published_at: datetime | None
    post_url: str | None
    publish_mode: str
    status: str
    export_asset_id: uuid.UUID | None
    error_message: str | None
    data_mode: str
    created_at: datetime


class PublishedIn(BaseModel):
    post_url: str = Field(min_length=10, max_length=500)
    published_at: datetime | None = None


class CaptionCheckIn(BaseModel):
    channel_id: uuid.UUID
    caption: str
    hashtags: list[str] = Field(default_factory=list)


@router.get("/calendar", response_model=list[PubOut])
def calendar(date_from: datetime | None = None, date_to: datetime | None = None, channel_id: uuid.UUID | None = None,
             ctx: Ctx = Depends(require("publish.view"))):
    return service.calendar(ctx, date_from, date_to, channel_id)


@router.get("/approved-videos", response_model=list[ProjectOut])
def approved(ctx: Ctx = Depends(require("publish.view"))):
    return service.approved_videos(ctx)


@router.post("/check-caption")
def check_caption(data: CaptionCheckIn, ctx: Ctx = Depends(require("publish.view"))):
    return {"findings": service.check_caption(ctx, data.channel_id, data.caption, data.hashtags)}


@router.post("", response_model=PubOut, status_code=201)
def create(data: PubIn, ctx: Ctx = Depends(require("publish.manage"))):
    pub = service.create_publication(ctx, data.project_id, platform=data.platform, caption=data.caption,
                                     hashtags=data.hashtags, scheduled_at=data.scheduled_at, publish_mode=data.publish_mode)
    ctx.db.commit()
    return pub


@router.patch("/{pid}", response_model=PubOut)
def update(pid: uuid.UUID, data: PubPatch, ctx: Ctx = Depends(require("publish.manage"))):
    pub = service.update_publication(ctx, pid, data.model_dump(exclude_unset=True))
    ctx.db.commit()
    return pub


@router.post("/{pid}/export")
def export(pid: uuid.UUID, ctx: Ctx = Depends(require("publish.manage"))):
    a = service.export_package(ctx, pid)
    ctx.db.commit()
    return {"asset_id": str(a.id), "download_url": f"/api/v1/assets/{a.id}/content?download=true"}


@router.post("/{pid}/mark-published", response_model=PubOut)
def mark_published(pid: uuid.UUID, data: PublishedIn, ctx: Ctx = Depends(require("publish.execute"))):
    pub = service.mark_published(ctx, pid, data.post_url, data.published_at)
    ctx.db.commit()
    return pub


@router.post("/{pid}/publish-api", response_model=PubOut)
def publish_api(pid: uuid.UUID, ctx: Ctx = Depends(require("publish.execute"))):
    pub = service.publish_via_api(ctx, pid)
    ctx.db.commit()
    return pub


@router.post("/{pid}/cancel", response_model=PubOut)
def cancel(pid: uuid.UUID, ctx: Ctx = Depends(require("publish.manage"))):
    pub = service.cancel_publication(ctx, pid)
    ctx.db.commit()
    return pub
