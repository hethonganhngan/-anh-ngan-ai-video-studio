"""B04 API — Prompt templates & phiên bản."""
import uuid
from datetime import datetime

from app.api.deps import require
from app.api.schemas import ORM
from app.core.context import Ctx
from app.core.errors import NotFound
from app.modules.prompts import service
from app.modules.prompts.models import PromptTemplate, PromptVersion
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

router = APIRouter(prefix="/prompts", tags=["B04 Prompt Engine"])


class VersionOut(ORM):
    id: uuid.UUID
    template_id: uuid.UUID
    version_no: int
    content: str
    negative_prompt: str
    rules: list
    status: str
    data_mode: str
    change_note: str
    source_lesson_id: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime


class VersionIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    negative_prompt: str = Field(default="", max_length=5000)
    rules: list[str] = Field(default_factory=list)
    change_note: str = Field(default="", max_length=255)


def _tpl_out(ctx: Ctx, t: PromptTemplate) -> dict:
    active = service.active_version(ctx, t) if (t.active_version_id or t.demo_active_version_id) else None
    return {"id": str(t.id), "code": t.code, "name": t.name, "agent_code": t.agent_code, "purpose": t.purpose,
            "active_version_id": str(active.id) if active else None, "active_version_no": active.version_no if active else None,
            "production_active_version_id": str(t.active_version_id) if t.active_version_id else None,
            "demo_active_version_id": str(t.demo_active_version_id) if t.demo_active_version_id else None}


@router.get("/templates")
def templates(ctx: Ctx = Depends(require("prompt.view"))):
    return [_tpl_out(ctx, t) for t in ctx.db.scalars(select(PromptTemplate).order_by(PromptTemplate.code)).all()]


@router.get("/templates/{template_id}/versions", response_model=list[VersionOut])
def versions(template_id: uuid.UUID, ctx: Ctx = Depends(require("prompt.view"))):
    return ctx.db.scalars(select(PromptVersion).where(PromptVersion.template_id == template_id)
                          .order_by(PromptVersion.version_no.desc())).all()


@router.post("/templates/{template_id}/versions", response_model=VersionOut, status_code=201)
def create_version(template_id: uuid.UUID, data: VersionIn, ctx: Ctx = Depends(require("prompt.edit"))):
    v = service.create_version(ctx, template_id, content=data.content, negative_prompt=data.negative_prompt,
                               rules=data.rules, change_note=data.change_note)
    ctx.db.commit()
    return v


@router.post("/versions/{version_id}/activate", response_model=VersionOut)
def activate(version_id: uuid.UUID, ctx: Ctx = Depends(require("prompt.approve"))):
    v = service.approve_and_activate(ctx, version_id)
    ctx.db.commit()
    return v


@router.get("/versions/{version_id}", response_model=VersionOut)
def get_version(version_id: uuid.UUID, ctx: Ctx = Depends(require("prompt.view"))):
    v = ctx.db.get(PromptVersion, version_id)
    if v is None:
        raise NotFound("Không tìm thấy phiên bản")
    return v
