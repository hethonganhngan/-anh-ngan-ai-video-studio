"""B01 API — dự án, lô, kanban, workflow."""
import uuid
from datetime import datetime

from app.api.deps import require
from app.api.schemas import Page
from app.core.context import Ctx
from app.modules.projects import service
from app.modules.projects.models import Channel
from app.modules.projects.schemas import (
    CreateResult,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    TransitionIn,
    WorkflowEventOut,
)
from app.workflows import state_machine as sm
from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

router = APIRouter(prefix="/projects", tags=["B01 Project Manager"])


class EstimateIn(BaseModel):
    duration_sec: int = 32
    quantity: int = 1
    video_provider_code: str = "mock"
    budget_limit: float = 0


@router.get("/workflow")
def workflow_definition():
    return sm.describe()


@router.post("/estimate")
def estimate(data: EstimateIn, ctx: Ctx = Depends(require("project.view"))):
    from decimal import Decimal

    return service.estimate(ctx, duration_sec=data.duration_sec, quantity=data.quantity,
                            provider_code=data.video_provider_code, budget_limit=Decimal(str(data.budget_limit)))


@router.post("", response_model=CreateResult, status_code=201)
def create(data: ProjectCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
           ctx: Ctx = Depends(require("project.create"))):
    if idempotency_key and not data.idempotency_key:
        data.idempotency_key = idempotency_key
    from sqlalchemy.exc import IntegrityError

    try:
        result = service.create_projects(ctx, data)
        ctx.db.commit()
    except IntegrityError:
        # Request trùng idempotency_key chạy song song: bản kia đã commit trước → trả về bản đã có
        ctx.db.rollback()
        if not data.idempotency_key:
            raise
        result = service.create_projects(ctx, data)
        if not result["duplicate"]:
            raise
    return result


@router.get("", response_model=Page[ProjectOut])
def list_(status: str | None = None, channel_id: uuid.UUID | None = None, owner_id: uuid.UUID | None = None,
          batch_id: uuid.UUID | None = None, q: str | None = None, date_from: datetime | None = None,
          date_to: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
          ctx: Ctx = Depends(require("project.view"))):
    items, total = service.list_projects(ctx, status=status, channel_id=channel_id, owner_id=owner_id, q=q,
                                         batch_id=batch_id, page=page, page_size=page_size, date_from=date_from,
                                         date_to=date_to)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/kanban")
def kanban(channel_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("project.view"))):
    data = service.kanban(ctx, channel_id)
    return {"columns": [{**c, "items": [ProjectOut.model_validate(p).model_dump(mode="json") for p in c["items"]]}
                        for c in data["columns"]]}


@router.get("/channels")
def channels_mini(ctx: Ctx = Depends(require("project.view"))):
    from sqlalchemy import select

    return [{"id": str(c.id), "code": c.code, "name": c.name}
            for c in ctx.db.scalars(select(Channel).where(Channel.deleted_at.is_(None), Channel.is_active)).all()]


@router.get("/{project_id}", response_model=ProjectOut)
def get(project_id: uuid.UUID, ctx: Ctx = Depends(require("project.view"))):
    return service.get_project(ctx, project_id)


@router.get("/{project_id}/overview")
def overview(project_id: uuid.UUID, ctx: Ctx = Depends(require("project.view"))):
    from app.workflows.orchestrator import project_overview

    return project_overview(ctx, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update(project_id: uuid.UUID, data: ProjectUpdate, ctx: Ctx = Depends(require("project.edit"))):
    p = service.update_project(ctx, project_id, data)
    ctx.db.commit()
    return p


@router.get("/{project_id}/events", response_model=list[WorkflowEventOut])
def events(project_id: uuid.UUID, ctx: Ctx = Depends(require("project.view"))):
    return service.events(ctx, project_id)


@router.post("/{project_id}/cancel", response_model=ProjectOut)
def cancel(project_id: uuid.UUID, data: TransitionIn, ctx: Ctx = Depends(require("project.cancel"))):
    p = service.cancel_project(ctx, project_id, data.note)
    ctx.db.commit()
    return p


@router.post("/{project_id}/retry")
def retry(project_id: uuid.UUID, data: TransitionIn, ctx: Ctx = Depends(require("project.edit"))):
    from app.workflows.orchestrator import retry_project

    result = retry_project(ctx, project_id, data.note)
    ctx.db.commit()
    return result


@router.post("/{project_id}/advance")
def advance(project_id: uuid.UUID, ctx: Ctx = Depends(require("project.edit"))):
    """A01 AI Director: chạy các bước tự động kế tiếp theo mức tự động hoá (dừng ở mọi điểm cần con người duyệt)."""
    from app.workflows.orchestrator import advance_project

    result = advance_project(ctx, project_id)
    ctx.db.commit()
    return result


@router.post("/{project_id}/resolve-manual")
def resolve_manual(project_id: uuid.UUID, data: TransitionIn, ctx: Ctx = Depends(require("project.edit"))):
    from app.workflows.orchestrator import resolve_manual_action

    result = resolve_manual_action(ctx, project_id, data.note)
    ctx.db.commit()
    return result
