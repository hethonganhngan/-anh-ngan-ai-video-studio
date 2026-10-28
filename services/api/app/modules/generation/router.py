"""B05 API — Video Production (M05)."""
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel

from app.api.deps import require
from app.api.schemas import ORM, Page
from app.core.context import Ctx
from app.media.router import save_upload
from app.media.schemas import AssetOut
from app.media.storage import safe_remove
from app.modules.generation import service
from app.modules.scripts.schemas import SceneOut
from app.providers.video.registry import list_video_providers

router = APIRouter(tags=["B05 Video Generation Manager"])


class JobOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    scene_id: uuid.UUID
    scene_version_no: int
    provider_code: str
    status: str
    attempt_no: int
    max_retries: int
    provider_job_id: str | None
    estimated_cost: Decimal
    actual_cost: Decimal
    result_asset_id: uuid.UUID | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    log: list
    data_mode: str


class QueueIn(BaseModel):
    scene_ids: list[uuid.UUID] | None = None


class SelectIn(BaseModel):
    asset_id: uuid.UUID


@router.get("/video-providers")
def providers(ctx: Ctx = Depends(require("project.view"))):
    return list_video_providers(ctx.db, ctx.mode)


@router.post("/projects/{project_id}/validate-assets")
def validate_assets(project_id: uuid.UUID, ctx: Ctx = Depends(require("generation.run"))):
    report = service.validate_assets(ctx, project_id)
    ctx.db.commit()
    return report


@router.post("/projects/{project_id}/generate", response_model=list[JobOut])
def generate(project_id: uuid.UUID, data: QueueIn, ctx: Ctx = Depends(require("generation.run"))):
    jobs = service.queue_generation(ctx, project_id, data.scene_ids)
    ids = [j.id for j in jobs]
    ctx.db.commit()
    ctx.db.expire_all()
    from app.modules.generation.models import GenerationJob

    return [ctx.db.get(GenerationJob, i) for i in ids]


@router.get("/projects/{project_id}/production")
def production(project_id: uuid.UUID, ctx: Ctx = Depends(require("project.view"))):
    rows = service.scene_production(ctx, project_id)
    return [{"scene": SceneOut.model_validate(r["scene"]).model_dump(mode="json"),
             "jobs": [JobOut.model_validate(j).model_dump(mode="json") for j in r["jobs"]],
             "outputs": [AssetOut.model_validate(a).model_dump(mode="json") for a in r["outputs"]],
             "attempts_this_version": r["attempts_this_version"], "cost_total": r["cost_total"]} for r in rows]


@router.get("/generation-jobs", response_model=Page[JobOut])
def jobs(project_id: uuid.UUID | None = None, status: str | None = None, page: int = Query(1, ge=1),
         page_size: int = Query(100, ge=1, le=500), ctx: Ctx = Depends(require("project.view"))):
    items, total = service.list_jobs(ctx, project_id=project_id, status=status, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/generation-jobs/{job_id}/cancel", response_model=JobOut)
def cancel(job_id: uuid.UUID, ctx: Ctx = Depends(require("generation.cancel"))):
    job = service.cancel_job(ctx, job_id)
    ctx.db.commit()
    return job


@router.post("/scenes/{scene_id}/regenerate", response_model=list[JobOut])
def regenerate(scene_id: uuid.UUID, ctx: Ctx = Depends(require("generation.run"))):
    from app.modules.scripts.models import Scene

    scene = ctx.db.get(Scene, scene_id)
    if scene is None:
        from app.core.errors import NotFound

        raise NotFound("Không tìm thấy cảnh")
    jobs = service.queue_generation(ctx, scene.project_id, [scene_id])
    ids = [j.id for j in jobs]
    ctx.db.commit()
    ctx.db.expire_all()
    from app.modules.generation.models import GenerationJob

    return [ctx.db.get(GenerationJob, i) for i in ids]


@router.post("/scenes/{scene_id}/import-flow")
async def import_flow(scene_id: uuid.UUID, file: UploadFile = File(...), actual_cost: Decimal = Form(Decimal(0)),
                      note: str = Form(""), ctx: Ctx = Depends(require("generation.import"))):
    path = await save_upload(file)
    try:
        result = service.import_flow_clip(ctx, scene_id, path, file.filename or "flow.mp4", actual_cost, note)
        ctx.db.commit()
        return result
    finally:
        safe_remove(path)


@router.post("/scenes/{scene_id}/select-output", response_model=SceneOut)
def select_output(scene_id: uuid.UUID, data: SelectIn, ctx: Ctx = Depends(require("generation.run"))):
    s = service.select_scene_version(ctx, scene_id, data.asset_id)
    ctx.db.commit()
    return s


@router.post("/jobs/recover")
def recover(ctx: Ctx = Depends(require("generation.run"))):
    from app.workflows.jobs import recover_stuck_jobs

    return recover_stuck_jobs(older_than_minutes=5)
