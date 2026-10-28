"""B09 API — AI Lessons Learned (M09)."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import require
from app.api.schemas import ORM, Page
from app.core.context import Ctx
from app.modules.learning import service

router = APIRouter(prefix="/lessons", tags=["B09 AI Lessons Learned Engine"])


class Change(BaseModel):
    template_code: str | None = None
    append_negative: str = ""
    append_rule: str = ""


class LessonIn(BaseModel):
    lesson_type: str
    title: str = Field(min_length=3, max_length=255)
    lesson: str = Field(min_length=3)
    root_cause: str = ""
    capa_summary: str = ""
    verification_summary: str = ""
    channel_id: uuid.UUID | None = None
    character_id: uuid.UUID | None = None
    error_category: str | None = None
    provider_code: str | None = None
    prompt_example: str = ""
    proposed_change: Change | None = None
    tags: list[str] = Field(default_factory=list)


class LessonPatch(BaseModel):
    title: str | None = None
    lesson: str | None = None
    root_cause: str | None = None
    capa_summary: str | None = None
    verification_summary: str | None = None
    error_category: str | None = None
    provider_code: str | None = None
    prompt_example: str | None = None
    proposed_change: Change | None = None
    tags: list[str] | None = None


class LessonOut(ORM):
    id: uuid.UUID
    code: str
    feedback_case_id: uuid.UUID | None
    lesson_type: str
    title: str
    lesson: str
    root_cause: str
    capa_summary: str
    verification_summary: str
    channel_id: uuid.UUID | None
    character_id: uuid.UUID | None
    error_category: str | None
    provider_code: str | None
    prompt_example: str
    proposed_change: dict
    tags: list
    status: str
    version_no: int
    history: list
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    applied_at: datetime | None
    applied_prompt_version_id: uuid.UUID | None
    previous_prompt_version_id: uuid.UUID | None
    rolled_back_at: datetime | None
    created_at: datetime


class ReviewIn(BaseModel):
    approve: bool
    comment: str = ""


class RollbackIn(BaseModel):
    reason: str = Field(min_length=3)


def _clean(d: dict) -> dict:
    if d.get("proposed_change") and not d["proposed_change"].get("template_code"):
        d["proposed_change"] = {}
    return d


@router.get("", response_model=Page[LessonOut])
def search(q: str | None = None, channel_id: uuid.UUID | None = None, character_id: uuid.UUID | None = None,
           error_category: str | None = None, provider_code: str | None = None, lesson_type: str | None = None,
           status: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, le=200),
           ctx: Ctx = Depends(require("lesson.view"))):
    items, total = service.search(ctx, q=q, channel_id=channel_id, character_id=character_id, error_category=error_category,
                                  provider_code=provider_code, lesson_type=lesson_type, status=status, page=page,
                                  page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=LessonOut, status_code=201)
def create(data: LessonIn, ctx: Ctx = Depends(require("lesson.create"))):
    x = service.create_lesson(ctx, _clean(data.model_dump()))
    ctx.db.commit()
    return x


@router.get("/{lid}", response_model=LessonOut)
def get(lid: uuid.UUID, ctx: Ctx = Depends(require("lesson.view"))):
    return service.get_lesson(ctx, lid)


@router.patch("/{lid}", response_model=LessonOut)
def update(lid: uuid.UUID, data: LessonPatch, ctx: Ctx = Depends(require("lesson.create"))):
    x = service.update_lesson(ctx, lid, _clean(data.model_dump(exclude_unset=True)))
    ctx.db.commit()
    return x


@router.post("/{lid}/submit", response_model=LessonOut)
def submit(lid: uuid.UUID, ctx: Ctx = Depends(require("lesson.create"))):
    x = service.submit_lesson(ctx, lid)
    ctx.db.commit()
    return x


@router.post("/{lid}/review", response_model=LessonOut)
def review(lid: uuid.UUID, data: ReviewIn, ctx: Ctx = Depends(require("lesson.approve"))):
    x = service.review_lesson(ctx, lid, data.approve, data.comment)
    ctx.db.commit()
    return x


@router.post("/{lid}/apply", response_model=LessonOut)
def apply(lid: uuid.UUID, ctx: Ctx = Depends(require("lesson.apply"))):
    service.apply_lesson(ctx, lid)
    ctx.db.commit()
    return service.get_lesson(ctx, lid)


@router.post("/{lid}/rollback", response_model=LessonOut)
def rollback(lid: uuid.UUID, data: RollbackIn, ctx: Ctx = Depends(require("lesson.apply"))):
    x = service.rollback_lesson(ctx, lid, data.reason)
    ctx.db.commit()
    return x


@router.get("/for-project/{project_id}", response_model=list[LessonOut])
def for_project(project_id: uuid.UUID, ctx: Ctx = Depends(require("lesson.view"))):
    from app.modules.projects.service import get_project

    return service.relevant_for_project(ctx, get_project(ctx, project_id))
