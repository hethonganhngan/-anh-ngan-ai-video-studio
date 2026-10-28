"""B07 API — Quality Control (M07)."""
import uuid
from datetime import datetime

from app.api.deps import require
from app.api.schemas import ORM
from app.core.context import Ctx
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectOut
from app.modules.quality import service
from app.modules.quality.criteria import CRITERIA
from app.modules.quality.models import QCFinding
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

router = APIRouter(tags=["B07 Quality Control Engine"])


class FindingOut(ORM):
    id: uuid.UUID
    qc_review_id: uuid.UUID
    project_id: uuid.UUID
    scene_id: uuid.UUID | None
    criterion: str
    severity: str
    description: str
    evidence: dict
    status: str
    resolution_note: str
    resolved_at: datetime | None
    feedback_case_id: uuid.UUID | None
    created_at: datetime


class ReviewOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    render_id: uuid.UUID | None
    scene_id: uuid.UUID | None
    review_type: str
    reviewer_type: str
    reviewer_id: uuid.UUID | None
    scores: dict
    total_score: float
    pending_manual: list
    automated_checks: dict
    has_critical: bool
    result: str
    notes: str
    created_at: datetime


class ApprovalOut(ORM):
    id: uuid.UUID
    render_id: uuid.UUID | None
    approver_id: uuid.UUID
    decision: str
    comment: str
    created_at: datetime


class SceneReviewIn(BaseModel):
    passed: bool
    notes: str = Field(default="", max_length=2000)
    severity: str | None = None
    criterion: str = "character"


class ScoreItem(BaseModel):
    score: float = Field(ge=0, le=10)
    note: str = ""


class NewFinding(BaseModel):
    criterion: str
    severity: str
    description: str = Field(min_length=3, max_length=2000)
    scene_id: uuid.UUID | None = None


class FinalReviewIn(BaseModel):
    scores: dict[str, ScoreItem]
    notes: str = Field(default="", max_length=4000)
    findings: list[NewFinding] = Field(default_factory=list)


class ResolveIn(BaseModel):
    action: str = "RESOLVE"
    note: str = Field(min_length=3, max_length=2000)


class ApprovalIn(BaseModel):
    decision: str
    comment: str = Field(default="", max_length=2000)


@router.get("/qc/criteria")
def criteria():
    return CRITERIA


@router.get("/qc/queue")
def queue(ctx: Ctx = Depends(require("qc.view"))):
    items = ctx.db.scalars(select(Project).where(Project.data_mode == ctx.mode, Project.deleted_at.is_(None),
                                                 Project.status.in_(["SCENE_QC", "FINAL_QC", "APPROVAL_PENDING"]))
                           .order_by(Project.updated_at.desc())).all()
    counts = dict(ctx.db.execute(select(QCFinding.project_id, func.count()).where(QCFinding.status == "OPEN")
                                 .group_by(QCFinding.project_id)).all())
    return [{**ProjectOut.model_validate(p).model_dump(mode="json"), "open_findings": counts.get(p.id, 0)} for p in items]


@router.get("/projects/{project_id}/qc")
def project_qc(project_id: uuid.UUID, ctx: Ctx = Depends(require("qc.view"))):
    d = service.latest_reviews(ctx, project_id)
    r = d["render"]
    return {
        "project": ProjectOut.model_validate(d["project"]).model_dump(mode="json"),
        "render": {"id": str(r.id), "version_no": r.version_no, "video_asset_id": str(r.video_asset_id),
                   "thumbnail_asset_id": str(r.thumbnail_asset_id) if r.thumbnail_asset_id else None,
                   "subtitle_asset_id": str(r.subtitle_asset_id) if r.subtitle_asset_id else None,
                   "duration_sec": r.duration_sec, "width": r.width, "height": r.height, "status": r.status,
                   "probe": r.probe} if r else None,
        "agent_final": ReviewOut.model_validate(d["agent_final"]).model_dump(mode="json") if d["agent_final"] else None,
        "reviews": [ReviewOut.model_validate(x).model_dump(mode="json") for x in d["reviews"]],
        "findings": [FindingOut.model_validate(x).model_dump(mode="json") for x in d["findings"]],
        "approvals": [ApprovalOut.model_validate(x).model_dump(mode="json") for x in d["approvals"]],
        "criteria": d["criteria"], "policy": d["policy"],
    }


@router.post("/scenes/{scene_id}/qc", response_model=ReviewOut)
def scene_review(scene_id: uuid.UUID, data: SceneReviewIn, ctx: Ctx = Depends(require("qc.review"))):
    r = service.human_scene_review(ctx, scene_id, data.passed, data.notes, data.severity, data.criterion)
    ctx.db.commit()
    return r


@router.post("/projects/{project_id}/qc/scene-check")
def rerun_scene_qc(project_id: uuid.UUID, ctx: Ctx = Depends(require("qc.review"))):
    from app.modules.projects.service import lock_project

    p = lock_project(ctx, project_id)
    from app.core.errors import InvalidTransition

    if p.status != "SCENE_QC":
        raise InvalidTransition("Chỉ chạy QC cảnh ở trạng thái SCENE_QC")
    res = service.run_scene_qc(ctx, p)
    ctx.db.commit()
    return res


@router.post("/projects/{project_id}/qc/final", response_model=ReviewOut)
def final_review(project_id: uuid.UUID, data: FinalReviewIn, ctx: Ctx = Depends(require("qc.review"))):
    r = service.submit_final_review(ctx, project_id, {k: v.model_dump() for k, v in data.scores.items()}, data.notes,
                                    [f.model_dump() for f in data.findings])
    ctx.db.commit()
    return r


@router.post("/qc-findings/{finding_id}/resolve", response_model=FindingOut)
def resolve(finding_id: uuid.UUID, data: ResolveIn, ctx: Ctx = Depends(require("qc.waive"))):
    f = service.resolve_finding(ctx, finding_id, data.action, data.note)
    ctx.db.commit()
    return f


@router.post("/qc-findings/{finding_id}/feedback")
def finding_to_feedback(finding_id: uuid.UUID, ctx: Ctx = Depends(require("feedback.create"))):
    from app.core.errors import NotFound
    from app.modules.feedback.service import create_from_finding

    f = ctx.db.get(QCFinding, finding_id)
    if f is None:
        raise NotFound("Không tìm thấy lỗi QC")
    case = create_from_finding(ctx, f)
    ctx.db.commit()
    return {"feedback_case_id": str(case.id), "code": case.code}


@router.get("/qc/findings", response_model=list[FindingOut])
def findings(status: str | None = "OPEN", limit: int = Query(100, le=500), ctx: Ctx = Depends(require("qc.view"))):
    stmt = select(QCFinding).join(Project, Project.id == QCFinding.project_id).where(Project.data_mode == ctx.mode)
    if status:
        stmt = stmt.where(QCFinding.status == status)
    return ctx.db.scalars(stmt.order_by(QCFinding.created_at.desc()).limit(limit)).all()


@router.post("/projects/{project_id}/approve", response_model=ApprovalOut)
def approve(project_id: uuid.UUID, data: ApprovalIn, ctx: Ctx = Depends(require("project.approve"))):
    a = service.approve(ctx, project_id, data.decision, data.comment)
    ctx.db.commit()
    return a
