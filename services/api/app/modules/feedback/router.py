"""B08 API — Feedback Loop 360° (M08)."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import require
from app.api.schemas import ORM, Page
from app.core.context import Ctx
from app.modules.feedback import service

router = APIRouter(prefix="/feedback", tags=["B08 Feedback Loop Engine"])


class Evidence(BaseModel):
    type: str = "NOTE"
    ref: str = ""
    note: str = ""


class CaseIn(BaseModel):
    source: str
    category: str = "OTHER"
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    project_id: uuid.UUID | None = None
    scene_id: uuid.UUID | None = None
    channel_id: uuid.UUID | None = None
    character_id: uuid.UUID | None = None
    provider_code: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    evidence_class: str = "UNKNOWN"


class EventOut(ORM):
    id: uuid.UUID
    created_at: datetime
    step: str
    from_status: str | None
    to_status: str
    actor_type: str
    actor_ref: str | None
    note: str


class CaseOut(ORM):
    id: uuid.UUID
    code: str
    project_id: uuid.UUID | None
    scene_id: uuid.UUID | None
    channel_id: uuid.UUID | None
    character_id: uuid.UUID | None
    provider_code: str | None
    qc_finding_id: uuid.UUID | None
    source: str
    category: str
    title: str
    description: str
    evidence: list
    evidence_class: str
    priority: str | None
    status: str
    owner_id: uuid.UUID | None
    deadline: datetime | None
    kpi_name: str | None
    kpi_before: float | None
    kpi_after: float | None
    kpi_target: float | None
    approver_id: uuid.UUID | None
    reopen_count: int
    standardization_note: str
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RCAOut(ORM):
    id: uuid.UUID
    whys: list
    root_cause: str
    cause_category: str
    evidence_class: str
    confidence_pct: int
    is_current: bool
    created_at: datetime


class CAPAOut(ORM):
    id: uuid.UUID
    action_type: str
    description: str
    owner_id: uuid.UUID | None
    deadline: datetime | None
    status: str
    approved_by: uuid.UUID | None
    completed_at: datetime | None
    completion_evidence: list
    created_at: datetime


class VerificationOut(ORM):
    id: uuid.UUID
    method: str
    kpi_before: float | None
    kpi_after: float | None
    passed: bool
    evidence: list
    notes: str
    verified_by: uuid.UUID | None
    created_at: datetime


class ValidateIn(BaseModel):
    evidence_class: str
    evidence: list[Evidence] = Field(default_factory=list)
    note: str = ""


class TriageIn(BaseModel):
    priority: str
    owner_id: uuid.UUID
    deadline: datetime | None = None
    kpi_name: str | None = None
    kpi_before: float | None = None
    kpi_target: float | None = None
    note: str = ""


class Why(BaseModel):
    question: str = ""
    answer: str = ""


class RCAIn(BaseModel):
    whys: list[Why] = Field(min_length=1, max_length=5)
    root_cause: str = Field(min_length=3)
    cause_category: str = "OTHER"
    evidence_class: str = "HYPOTHESIS"
    confidence_pct: int = Field(default=50, ge=0, le=100)


class CAPAIn(BaseModel):
    action_type: str
    description: str = Field(min_length=3)
    owner_id: uuid.UUID | None = None
    deadline: datetime | None = None


class NoteIn(BaseModel):
    note: str = ""


class CompleteIn(BaseModel):
    evidence: list[Evidence] = Field(min_length=1)


class VerifyIn(BaseModel):
    method: str = Field(min_length=3)
    kpi_after: float | None = None
    passed: bool
    evidence: list[Evidence] = Field(min_length=1)
    notes: str = ""


class RestartIn(BaseModel):
    target: str = "RCA_PENDING"
    note: str = ""


class LessonChange(BaseModel):
    template_code: str | None = None
    append_negative: str = ""
    append_rule: str = ""


class StandardizeIn(BaseModel):
    note: str = Field(min_length=3)
    create_lesson: bool = True
    lesson_title: str | None = None
    lesson_type: str | None = None
    proposed_change: LessonChange | None = None


def _detail(ctx: Ctx, case_id) -> dict:
    d = service.case_detail(ctx, case_id)
    return {"case": CaseOut.model_validate(d["case"]).model_dump(mode="json"),
            "rca": [RCAOut.model_validate(x).model_dump(mode="json") for x in d["rca"]],
            "capa": [CAPAOut.model_validate(x).model_dump(mode="json") for x in d["capa"]],
            "verifications": [VerificationOut.model_validate(x).model_dump(mode="json") for x in d["verifications"]],
            "events": [EventOut.model_validate(x).model_dump(mode="json") for x in d["events"]],
            "overdue": d["overdue"],
            "allowed_next": sorted(service.TRANSITIONS.get(d["case"].status, set()))}


@router.get("/meta")
def meta():
    return {"statuses": service.STATUSES, "transitions": {k: sorted(v) for k, v in service.TRANSITIONS.items()},
            "steps": ["INTAKE", "VALIDATE", "TRIAGE", "ROOT CAUSE", "CAPA", "ASSIGN", "VERIFY", "STANDARDIZE"],
            "sources": sorted(service.SOURCES), "categories": sorted(service.CATEGORIES),
            "priorities": list(service.PRIORITY_DAYS), "evidence_classes": sorted(service.EVIDENCE_CLASSES)}


@router.get("/stats")
def stats(ctx: Ctx = Depends(require("feedback.view"))):
    return service.stats(ctx)


@router.get("", response_model=Page[CaseOut])
def list_(status: str | None = None, priority: str | None = None, source: str | None = None,
          project_id: uuid.UUID | None = None, category: str | None = None, q: str | None = None,
          page: int = Query(1, ge=1), page_size: int = Query(50, le=200), ctx: Ctx = Depends(require("feedback.view"))):
    items, total = service.list_cases(ctx, status=status, priority=priority, source=source, project_id=project_id,
                                      category=category, q=q, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("", status_code=201)
def create(data: CaseIn, ctx: Ctx = Depends(require("feedback.create"))):
    c = service.create_case(ctx, data.model_dump())
    ctx.db.commit()
    return _detail(ctx, c.id)


@router.get("/{case_id}")
def detail(case_id: uuid.UUID, ctx: Ctx = Depends(require("feedback.view"))):
    return _detail(ctx, case_id)


@router.post("/{case_id}/validate")
def validate(case_id: uuid.UUID, data: ValidateIn, ctx: Ctx = Depends(require("feedback.manage"))):
    service.validate_case(ctx, case_id, evidence_class=data.evidence_class,
                          evidence=[e.model_dump() for e in data.evidence], note=data.note)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/{case_id}/triage")
def triage(case_id: uuid.UUID, data: TriageIn, ctx: Ctx = Depends(require("feedback.manage"))):
    service.triage(ctx, case_id, priority=data.priority, owner_id=data.owner_id, deadline=data.deadline,
                   kpi_name=data.kpi_name, kpi_before=data.kpi_before, kpi_target=data.kpi_target, note=data.note)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/{case_id}/rca/suggest")
def rca_suggest(case_id: uuid.UUID, ctx: Ctx = Depends(require("feedback.manage"))):
    res = service.suggest_rca(ctx, case_id)
    ctx.db.commit()
    return res


@router.post("/{case_id}/rca")
def rca(case_id: uuid.UUID, data: RCAIn, ctx: Ctx = Depends(require("feedback.manage"))):
    service.record_rca(ctx, case_id, whys=[w.model_dump() for w in data.whys], root_cause=data.root_cause,
                       cause_category=data.cause_category, evidence_class=data.evidence_class,
                       confidence_pct=data.confidence_pct)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/{case_id}/capa")
def add_capa(case_id: uuid.UUID, data: CAPAIn, ctx: Ctx = Depends(require("feedback.manage"))):
    service.add_capa(ctx, case_id, action_type=data.action_type, description=data.description, owner_id=data.owner_id,
                     deadline=data.deadline)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/{case_id}/capa/approve")
def approve_capa(case_id: uuid.UUID, data: NoteIn, ctx: Ctx = Depends(require("feedback.approve"))):
    service.approve_capa(ctx, case_id, data.note)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/{case_id}/start")
def start(case_id: uuid.UUID, data: NoteIn, ctx: Ctx = Depends(require("feedback.manage"))):
    service.start_actions(ctx, case_id, data.note)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/capa/{capa_id}/complete")
def complete_capa(capa_id: uuid.UUID, data: CompleteIn, ctx: Ctx = Depends(require("feedback.view"))):
    a = service.complete_capa(ctx, capa_id, [e.model_dump() for e in data.evidence])
    ctx.db.commit()
    return _detail(ctx, a.feedback_case_id)


@router.post("/{case_id}/submit-verification")
def submit_verification(case_id: uuid.UUID, data: NoteIn, ctx: Ctx = Depends(require("feedback.manage"))):
    service.submit_for_verification(ctx, case_id, data.note)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/{case_id}/verify")
def verify(case_id: uuid.UUID, data: VerifyIn, ctx: Ctx = Depends(require("feedback.verify"))):
    service.verify(ctx, case_id, method=data.method, kpi_after=data.kpi_after, passed=data.passed,
                   evidence=[e.model_dump() for e in data.evidence], notes=data.notes)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/{case_id}/restart")
def restart(case_id: uuid.UUID, data: RestartIn, ctx: Ctx = Depends(require("feedback.manage"))):
    service.reopen_restart(ctx, case_id, data.target, data.note)
    ctx.db.commit()
    return _detail(ctx, case_id)


@router.post("/{case_id}/standardize")
def standardize(case_id: uuid.UUID, data: StandardizeIn, ctx: Ctx = Depends(require("feedback.close"))):
    lesson = {"title": data.lesson_title, "lesson_type": data.lesson_type,
              "proposed_change": data.proposed_change.model_dump() if data.proposed_change and data.proposed_change.template_code else {}}
    res = service.standardize(ctx, case_id, note=data.note, create_lesson=data.create_lesson,
                              lesson={k: v for k, v in lesson.items() if v})
    ctx.db.commit()
    out = _detail(ctx, case_id)
    out["lesson_id"] = str(res["lesson"].id) if res["lesson"] else None
    return out


@router.post("/{case_id}/close")
def close(case_id: uuid.UUID, data: NoteIn, ctx: Ctx = Depends(require("feedback.close"))):
    service.close_case(ctx, case_id, data.note)
    ctx.db.commit()
    return _detail(ctx, case_id)
