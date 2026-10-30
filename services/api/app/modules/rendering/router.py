"""B06 API — AI Video Editor (M06)."""
import uuid
from datetime import datetime

from app.api.deps import require
from app.api.schemas import ORM
from app.core.context import Ctx
from app.modules.rendering import service
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

router = APIRouter(tags=["B06 Render Engine"])


class ClipIn(BaseModel):
    scene_id: uuid.UUID
    asset_id: uuid.UUID | None
    trim_start: float = Field(default=0, ge=0)
    trim_end: float | None = Field(default=None, gt=0)
    volume: float = Field(default=1.0, ge=0, le=2)


class AudioTrackIn(BaseModel):
    asset_id: uuid.UUID
    start: float = Field(default=0, ge=0)
    volume: float = Field(default=1.0, ge=0, le=2)


class MusicIn(BaseModel):
    asset_id: uuid.UUID
    volume: float = Field(default=0.15, ge=0, le=1)
    fade_out: float = Field(default=2.0, ge=0, le=10)


class LogoIn(BaseModel):
    asset_id: uuid.UUID
    position: str = "top_right"
    scale: float = Field(default=0.18, ge=0.05, le=0.5)
    opacity: float = Field(default=0.9, ge=0.1, le=1)


class SubtitleIn(BaseModel):
    enabled: bool = True
    burn_in: bool = True
    font_size: int = Field(default=10, ge=6, le=24)


class ThumbIn(BaseModel):
    time_sec: float = Field(default=1.0, ge=0)
    title: str | None = Field(default=None, max_length=80)


class TimelineIn(BaseModel):
    clips: list[ClipIn] = Field(min_length=1, max_length=30)
    subtitles: SubtitleIn = SubtitleIn()
    voiceover: list[AudioTrackIn] = Field(default_factory=list, max_length=5)
    music: MusicIn | None = None
    logo: LogoIn | None = None
    thumbnail: ThumbIn = ThumbIn()


class RenderOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    render_job_id: uuid.UUID
    version_no: int
    video_asset_id: uuid.UUID
    thumbnail_asset_id: uuid.UUID | None
    subtitle_asset_id: uuid.UUID | None
    duration_sec: float
    width: int
    height: int
    size_bytes: int
    probe: dict
    status: str
    created_at: datetime


class RenderJobOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    attempt_no: int
    max_retries: int
    error_message: str | None
    log: list
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


@router.get("/projects/{project_id}/timeline")
def get_timeline(project_id: uuid.UUID, ctx: Ctx = Depends(require("project.view"))):
    return service.get_timeline(ctx, project_id)


@router.put("/projects/{project_id}/timeline")
def save_timeline(project_id: uuid.UUID, data: TimelineIn, ctx: Ctx = Depends(require("editor.edit"))):
    tl = service.save_timeline(ctx, project_id, data.model_dump(mode="json"))
    ctx.db.commit()
    return tl


class VoiceoverIn(BaseModel):
    voice_profile_id: uuid.UUID | None = None
    scene_volume: float = Field(default=0.35, ge=0, le=1)


@router.post("/projects/{project_id}/voiceover/generate")
def generate_voiceover(project_id: uuid.UUID, data: VoiceoverIn, ctx: Ctx = Depends(require("editor.edit"))):
    """Tạo voice-over AI từ lời thoại các cảnh và gắn vào timeline (DEMO: Mock TTS; PRODUCTION: TTS thật)."""
    from app.modules.rendering.voiceover import generate_voiceover as gen

    res = gen(ctx, project_id, voice_profile_id=data.voice_profile_id, scene_volume=data.scene_volume)
    ctx.db.commit()
    return res


@router.post("/projects/{project_id}/timeline/reset")
def reset_timeline(project_id: uuid.UUID, ctx: Ctx = Depends(require("editor.edit"))):
    from app.modules.projects.service import lock_project

    p = lock_project(ctx, project_id)
    p.timeline = service.default_timeline(ctx, p)
    ctx.db.commit()
    return p.timeline


@router.post("/projects/{project_id}/render", response_model=RenderJobOut)
def render(project_id: uuid.UUID, ctx: Ctx = Depends(require("render.run"))):
    job = service.start_render(ctx, project_id, None)
    jid = job.id
    ctx.db.commit()
    ctx.db.expire_all()
    from app.modules.rendering.models import RenderJob

    return ctx.db.get(RenderJob, jid)


@router.get("/projects/{project_id}/renders", response_model=list[RenderOut])
def renders(project_id: uuid.UUID, ctx: Ctx = Depends(require("project.view"))):
    return service.renders(ctx, project_id)


@router.get("/render-jobs", response_model=list[RenderJobOut])
def render_jobs(project_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("project.view"))):
    return service.render_jobs(ctx, project_id)
