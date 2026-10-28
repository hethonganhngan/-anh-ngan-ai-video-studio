"""B08 — Feedback Loop Engine 360°.

8 bước: INTAKE → VALIDATE → TRIAGE → ROOT CAUSE → CAPA → ASSIGN → VERIFY → STANDARDIZE
Trạng thái: NEW → VALIDATED → RCA_PENDING → ACTION_APPROVED → IN_PROGRESS → VERIFY_PENDING → VERIFIED
            → STANDARDIZED → CLOSED; VERIFY_PENDING → REOPENED khi kiểm chứng không đạt.
Nguyên tắc: không đóng khi thiếu bằng chứng; không tuyên bố đã sửa khi chưa có kết quả kiểm chứng."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from app.agents.runner import run_agent
from app.core import audit
from app.core.codes import next_code
from app.core.context import Ctx
from app.core.errors import InvalidTransition, NotFound, ValidationFailed
from app.modules.administration.models import User
from app.modules.administration.service import notify
from app.modules.feedback.models import CAPAAction, FeedbackCase, FeedbackEvent, RootCauseAnalysis, VerificationResult

STATUSES = ["NEW", "VALIDATED", "RCA_PENDING", "ACTION_APPROVED", "IN_PROGRESS", "VERIFY_PENDING", "VERIFIED",
            "STANDARDIZED", "CLOSED", "REOPENED"]
TRANSITIONS = {
    "NEW": {"VALIDATED"}, "VALIDATED": {"RCA_PENDING"}, "RCA_PENDING": {"ACTION_APPROVED"},
    "ACTION_APPROVED": {"IN_PROGRESS"}, "IN_PROGRESS": {"VERIFY_PENDING"}, "VERIFY_PENDING": {"VERIFIED", "REOPENED"},
    "REOPENED": {"RCA_PENDING", "IN_PROGRESS"}, "VERIFIED": {"STANDARDIZED"}, "STANDARDIZED": {"CLOSED"}, "CLOSED": set(),
}
STEP_OF = {"NEW": "INTAKE", "VALIDATED": "VALIDATE", "RCA_PENDING": "TRIAGE", "ACTION_APPROVED": "CAPA",
           "IN_PROGRESS": "ASSIGN", "VERIFY_PENDING": "VERIFY", "VERIFIED": "VERIFY", "STANDARDIZED": "STANDARDIZE",
           "CLOSED": "STANDARDIZE", "REOPENED": "VERIFY"}
SOURCES = {"QC", "CUSTOMER", "INTERNAL", "ANALYTICS", "AGENT", "PUBLISHING"}
CATEGORIES = {"PROMPT", "CHARACTER", "VOICE", "PROVIDER", "SCRIPT", "AUDIO", "VISUAL", "BRAND", "COMPLIANCE", "PROCESS",
              "ASSET", "PERFORMANCE", "OTHER"}
EVIDENCE_CLASSES = {"FACT", "HYPOTHESIS", "UNKNOWN"}
PRIORITY_DAYS = {"P0": 1, "P1": 3, "P2": 7, "P3": 14}
CRITERION_TO_CATEGORY = {"hook": "SCRIPT", "script": "SCRIPT", "character": "CHARACTER", "setting": "PROMPT",
                         "visual": "VISUAL", "voice": "VOICE", "lipsync": "PROVIDER", "audio": "AUDIO", "brand": "BRAND",
                         "compliance": "COMPLIANCE"}


def _now():
    return datetime.now(timezone.utc)


def get_case(ctx: Ctx, case_id) -> FeedbackCase:
    c = ctx.db.get(FeedbackCase, case_id)
    if c is None or c.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy hồ sơ phản hồi")
    return c


def _lock(ctx: Ctx, case_id) -> FeedbackCase:
    c = ctx.db.scalar(select(FeedbackCase).where(FeedbackCase.id == case_id).with_for_update(key_share=True))
    if c is None or c.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy hồ sơ phản hồi")
    return c


def _move(ctx: Ctx, c: FeedbackCase, target: str, note: str = "") -> None:
    if target not in TRANSITIONS.get(c.status, set()):
        raise InvalidTransition(f"Hồ sơ không thể chuyển {c.status} → {target}",
                                details={"allowed": sorted(TRANSITIONS.get(c.status, set()))})
    ev = FeedbackEvent(feedback_case_id=c.id, step=STEP_OF[target], from_status=c.status, to_status=target,
                       actor_type=ctx.actor.type, actor_ref=ctx.actor.id, note=note[:2000])
    ctx.db.add(ev)
    audit.record(ctx, "feedback.transition", "feedback_case", c.id, before={"status": c.status}, after={"status": target, "note": note})
    c.status = target


def _validate_evidence(items: list[dict]) -> list[dict]:
    out = []
    for e in items or []:
        if not isinstance(e, dict) or not (e.get("ref") or e.get("note")):
            raise ValidationFailed("Bằng chứng phải có tham chiếu (asset/URL/ID) hoặc mô tả")
        out.append({"type": e.get("type", "NOTE"), "ref": str(e.get("ref", ""))[:500], "note": str(e.get("note", ""))[:1000],
                    "added_at": _now().isoformat()})
    return out


def create_case(ctx: Ctx, data: dict, *, actor_check: bool = True) -> FeedbackCase:
    if actor_check:
        ctx.require("feedback.create")
    if data.get("source") not in SOURCES:
        raise ValidationFailed("Nguồn phản hồi không hợp lệ")
    if data.get("category", "OTHER") not in CATEGORIES:
        raise ValidationFailed("Loại lỗi không hợp lệ")
    if not (data.get("title") or "").strip():
        raise ValidationFailed("Thiếu tiêu đề")
    c = FeedbackCase(
        code=next_code(ctx.db, FeedbackCase, "FB"), project_id=data.get("project_id"), scene_id=data.get("scene_id"),
        channel_id=data.get("channel_id"), character_id=data.get("character_id"), provider_code=data.get("provider_code"),
        qc_finding_id=data.get("qc_finding_id"), source=data["source"], category=data.get("category", "OTHER"),
        title=data["title"][:255], description=data.get("description", ""),
        evidence=_validate_evidence(data.get("evidence", [])), evidence_class=data.get("evidence_class", "UNKNOWN"),
        priority=data.get("priority"), status="NEW", reported_by=ctx.actor.user_uuid, data_mode=ctx.mode,
    )
    if c.project_id and not c.channel_id:
        from app.modules.projects.models import Project

        prj = ctx.db.get(Project, c.project_id)
        c.channel_id = prj.channel_id if prj else None
        c.provider_code = c.provider_code or (prj.video_provider_code if prj else None)
    ctx.db.add(c)
    ctx.db.flush()
    ctx.db.add(FeedbackEvent(feedback_case_id=c.id, step="INTAKE", from_status=None, to_status="NEW", actor_type=ctx.actor.type,
                             actor_ref=ctx.actor.id, note=f"Tiếp nhận từ {c.source}"))
    audit.record(ctx, "feedback.create", "feedback_case", c.id, after={"code": c.code, "source": c.source, "title": c.title})
    if c.priority == "P0":
        notify(ctx.db, ctx.mode, f"Feedback P0: {c.code}", c.title, level="CRITICAL", category="FEEDBACK", link=f"/feedback/{c.id}")
    return c


def triage_suggestion(severity: str, criterion: str) -> dict:
    """A08: gợi ý ưu tiên bằng quy tắc (không LLM)."""
    if criterion == "compliance" and severity == "CRITICAL":
        prio = "P0"
    elif severity == "CRITICAL":
        prio = "P1"
    elif severity == "MAJOR":
        prio = "P2"
    else:
        prio = "P3"
    return {"priority": prio, "category": CRITERION_TO_CATEGORY.get(criterion, "OTHER"),
            "reason": f"{severity} ở tiêu chí {criterion} → {prio}"}


def create_from_finding(ctx: Ctx, finding, auto: bool = False) -> FeedbackCase:
    """Mọi lỗi QC đều tạo được Feedback Case (A08 tự tạo cho lỗi CRITICAL)."""
    from app.modules.projects.models import Project

    if finding.feedback_case_id:
        return ctx.db.get(FeedbackCase, finding.feedback_case_id)
    if not auto:
        ctx.require("feedback.create")
    prj = ctx.db.get(Project, finding.project_id)
    sug = triage_suggestion(finding.severity, finding.criterion)

    def work(_llm, _actx):
        return {"result": sug}, None

    run_agent(ctx, "A08", "feedback.create_from_qc", work, project=prj, input_ref={"finding": str(finding.id)})
    c = create_case(ctx, {
        "source": "QC", "category": sug["category"], "title": f"[{finding.severity}] {finding.description}"[:255],
        "description": f"Phát hiện bởi QC ({finding.criterion}). {finding.description}", "project_id": finding.project_id,
        "scene_id": finding.scene_id, "qc_finding_id": finding.id, "evidence_class": "FACT",
        "evidence": [{"type": "QC_FINDING", "ref": str(finding.id), "note": finding.description}],
    }, actor_check=False)
    c.description += f"\nGợi ý ưu tiên của A08: {sug['priority']} ({sug['reason']})"
    finding.feedback_case_id = c.id
    return c


def validate_case(ctx: Ctx, case_id, *, evidence_class: str, evidence: list[dict], note: str) -> FeedbackCase:
    ctx.require("feedback.manage")
    c = _lock(ctx, case_id)
    if evidence_class not in EVIDENCE_CLASSES:
        raise ValidationFailed("Phân loại phải là FACT, HYPOTHESIS hoặc UNKNOWN")
    c.evidence = [*(c.evidence or []), *_validate_evidence(evidence)]
    if not c.evidence:
        raise ValidationFailed("Không thể xác thực hồ sơ khi chưa có bằng chứng", code="EVIDENCE_REQUIRED")
    c.evidence_class = evidence_class
    _move(ctx, c, "VALIDATED", note or f"Xác thực — {evidence_class}")
    return c


def triage(ctx: Ctx, case_id, *, priority: str, owner_id, deadline=None, kpi_name=None, kpi_before=None, kpi_target=None,
           note: str = "") -> FeedbackCase:
    ctx.require("feedback.manage")
    c = _lock(ctx, case_id)
    if priority not in PRIORITY_DAYS:
        raise ValidationFailed("Ưu tiên phải là P0–P3")
    owner = ctx.db.get(User, owner_id) if owner_id else None
    if owner is None or not owner.is_active:
        raise ValidationFailed("Phải chọn người phụ trách hợp lệ", code="OWNER_REQUIRED")
    c.priority = priority
    c.owner_id = owner.id
    c.deadline = deadline or (_now() + timedelta(days=PRIORITY_DAYS[priority]))
    c.kpi_name, c.kpi_before, c.kpi_target = kpi_name, kpi_before, kpi_target
    _move(ctx, c, "RCA_PENDING", note or f"Phân loại {priority}, giao {owner.full_name}")
    if priority == "P0":
        notify(ctx.db, ctx.mode, f"Feedback P0: {c.code}", c.title, level="CRITICAL", category="FEEDBACK",
               link=f"/feedback/{c.id}", user_id=owner.id)
    return c


def suggest_rca(ctx: Ctx, case_id) -> dict:
    """A08: gợi ý 5 Whys — LUÔN là HYPOTHESIS, cần người xác nhận bằng bằng chứng."""
    ctx.require("feedback.manage")
    c = get_case(ctx, case_id)
    templates = {
        "CHARACTER": ["Nhân vật khác nhau giữa các cảnh", "Prompt mỗi cảnh mô tả nhân vật không giống nhau",
                      "Character Lock chưa được đưa đủ vào prompt", "Template prompt thiếu khối mô tả cố định",
                      "Chưa có quy tắc bắt buộc tham chiếu Character Lock"],
        "AUDIO": ["Âm lượng video không đạt chuẩn", "Các clip có mức âm khác nhau", "Không chuẩn hoá loudness khi dựng",
                  "Thiếu bước kiểm tra LUFS trước phát hành", "Chưa có tiêu chuẩn âm thanh trong SOP"],
        "COMPLIANCE": ["Nội dung có từ/tuyên bố bị cấm", "Kịch bản không qua bộ lọc tuân thủ trước khi duyệt",
                       "Danh sách từ cấm chưa đầy đủ", "Brand DNA chưa cập nhật quy định", "Thiếu bước duyệt tuân thủ"],
    }
    whys = templates.get(c.category) or ["Lỗi xảy ra trong sản phẩm", "Bước sản xuất liên quan không phát hiện lỗi",
                                         "Thiếu kiểm tra ở bước đó", "Tiêu chuẩn chưa quy định rõ", "Quy trình chưa được chuẩn hoá"]

    def work(llm, _actx):
        res = llm.complete_json(system="A08 RCA", prompt=f"{c.title}\n{c.description}", schema={"type": "object"},
                                mock_fn=lambda: {"whys": [{"question": f"Tại sao {i + 1}?", "answer": w} for i, w in enumerate(whys)],
                                                 "root_cause": whys[-1], "evidence_class": "HYPOTHESIS", "confidence_pct": 40})
        return res.data, res

    run = run_agent(ctx, "A08", "feedback.rca_suggest", work, needs_llm=True, input_ref={"case": c.code})
    return {**run.output, "evidence_class": "HYPOTHESIS", "note": "Gợi ý của A08 — chưa phải kết luận"}


def record_rca(ctx: Ctx, case_id, *, whys: list[dict], root_cause: str, cause_category: str, evidence_class: str,
               confidence_pct: int) -> RootCauseAnalysis:
    ctx.require("feedback.manage")
    c = _lock(ctx, case_id)
    if c.status not in ("RCA_PENDING",):
        raise InvalidTransition("Chỉ ghi nguyên nhân gốc ở bước RCA_PENDING")
    filled = [w for w in whys if (w.get("answer") or "").strip()]
    if len(filled) < 3 or len(whys) > 5:
        raise ValidationFailed("5 Whys cần tối thiểu 3, tối đa 5 câu trả lời", code="RCA_INCOMPLETE")
    if not root_cause.strip():
        raise ValidationFailed("Thiếu nguyên nhân gốc")
    if evidence_class not in EVIDENCE_CLASSES:
        raise ValidationFailed("Phân loại bằng chứng không hợp lệ")
    if cause_category not in CATEGORIES:
        raise ValidationFailed("Nhóm nguyên nhân không hợp lệ")
    if evidence_class == "FACT" and confidence_pct < 70:
        raise ValidationFailed("FACT cần mức chắc chắn ≥ 70%")
    for old in ctx.db.scalars(select(RootCauseAnalysis).where(RootCauseAnalysis.feedback_case_id == c.id,
                                                              RootCauseAnalysis.is_current)):
        old.is_current = False
    r = RootCauseAnalysis(feedback_case_id=c.id, whys=filled, root_cause=root_cause, cause_category=cause_category,
                          evidence_class=evidence_class, confidence_pct=max(0, min(100, confidence_pct)),
                          created_by=ctx.actor.user_uuid)
    ctx.db.add(r)
    ctx.db.add(FeedbackEvent(feedback_case_id=c.id, step="ROOT CAUSE", from_status=c.status, to_status=c.status,
                             actor_type=ctx.actor.type, actor_ref=ctx.actor.id,
                             note=f"Nguyên nhân gốc ({evidence_class}, {confidence_pct}%): {root_cause[:300]}"))
    audit.record(ctx, "feedback.rca", "feedback_case", c.id, after={"root_cause": root_cause, "class": evidence_class})
    return r


def add_capa(ctx: Ctx, case_id, *, action_type: str, description: str, owner_id=None, deadline=None) -> CAPAAction:
    ctx.require("feedback.manage")
    c = _lock(ctx, case_id)
    if c.status not in ("RCA_PENDING", "REOPENED", "IN_PROGRESS"):
        raise InvalidTransition("Chỉ thêm CAPA sau khi phân tích nguyên nhân")
    if action_type not in ("CORRECTIVE", "PREVENTIVE"):
        raise ValidationFailed("Loại CAPA phải là CORRECTIVE hoặc PREVENTIVE")
    if not description.strip():
        raise ValidationFailed("Thiếu mô tả hành động")
    rca = ctx.db.scalar(select(RootCauseAnalysis).where(RootCauseAnalysis.feedback_case_id == c.id, RootCauseAnalysis.is_current))
    if rca is None:
        raise ValidationFailed("Phải có nguyên nhân gốc trước khi lập CAPA", code="RCA_REQUIRED")
    a = CAPAAction(feedback_case_id=c.id, action_type=action_type, description=description, owner_id=owner_id or c.owner_id,
                   deadline=deadline or c.deadline, status="PROPOSED" if c.status != "IN_PROGRESS" else "APPROVED")
    ctx.db.add(a)
    ctx.db.flush()
    audit.record(ctx, "feedback.capa_add", "capa_action", a.id, after={"case": c.code, "type": action_type})
    return a


def approve_capa(ctx: Ctx, case_id, note: str = "") -> FeedbackCase:
    ctx.require("feedback.approve")
    c = _lock(ctx, case_id)
    capas = ctx.db.scalars(select(CAPAAction).where(CAPAAction.feedback_case_id == c.id, CAPAAction.status == "PROPOSED")).all()
    if not any(a.action_type == "CORRECTIVE" for a in capas):
        raise ValidationFailed("Cần ít nhất 1 hành động khắc phục (CORRECTIVE)", code="CAPA_REQUIRED")
    rca = ctx.db.scalar(select(RootCauseAnalysis).where(RootCauseAnalysis.feedback_case_id == c.id, RootCauseAnalysis.is_current))
    if rca and rca.created_by and str(rca.created_by) == ctx.actor.id and ctx.actor.role_code != "SUPER_ADMIN":
        raise ValidationFailed("Người lập RCA không tự phê duyệt CAPA (nguyên tắc 4 mắt)", code="SELF_APPROVAL")
    for a in capas:
        a.status = "APPROVED"
        a.approved_by = ctx.actor.user_uuid
        a.approved_at = _now()
    c.approver_id = ctx.actor.user_uuid
    _move(ctx, c, "ACTION_APPROVED", note or f"Duyệt {len(capas)} CAPA")
    return c


def start_actions(ctx: Ctx, case_id, note: str = "") -> FeedbackCase:
    ctx.require("feedback.manage")
    c = _lock(ctx, case_id)
    capas = ctx.db.scalars(select(CAPAAction).where(CAPAAction.feedback_case_id == c.id, CAPAAction.status == "APPROVED")).all()
    missing = [a for a in capas if not a.owner_id or not a.deadline]
    if missing:
        raise ValidationFailed("Mọi CAPA phải có Owner và Deadline", code="CAPA_UNASSIGNED")
    for a in capas:
        a.status = "IN_PROGRESS"
    _move(ctx, c, "IN_PROGRESS", note or "Giao việc & bắt đầu thực hiện")
    return c


def complete_capa(ctx: Ctx, capa_id, evidence: list[dict]) -> CAPAAction:
    a = ctx.db.get(CAPAAction, capa_id)
    if a is None:
        raise NotFound("Không tìm thấy CAPA")
    c = _lock(ctx, a.feedback_case_id)
    if not (ctx.actor.has("feedback.manage") or (a.owner_id and str(a.owner_id) == ctx.actor.id)):
        ctx.require("feedback.manage")
    if a.status not in ("IN_PROGRESS", "APPROVED"):
        raise ValidationFailed("CAPA không ở trạng thái thực hiện")
    ev = _validate_evidence(evidence)
    if not ev:
        raise ValidationFailed("Hoàn thành CAPA cần bằng chứng", code="EVIDENCE_REQUIRED")
    a.status = "DONE"
    a.completed_at = _now()
    a.completion_evidence = ev
    audit.record(ctx, "feedback.capa_done", "capa_action", a.id, after={"case": c.code})
    return a


def submit_for_verification(ctx: Ctx, case_id, note: str = "") -> FeedbackCase:
    ctx.require("feedback.manage")
    c = _lock(ctx, case_id)
    capas = ctx.db.scalars(select(CAPAAction).where(CAPAAction.feedback_case_id == c.id, CAPAAction.status != "CANCELLED")).all()
    if not capas or any(a.status != "DONE" for a in capas):
        raise ValidationFailed("Tất cả CAPA phải hoàn thành trước khi kiểm chứng", code="CAPA_NOT_DONE")
    _move(ctx, c, "VERIFY_PENDING", note or "Chờ kiểm chứng hiệu quả")
    return c


def verify(ctx: Ctx, case_id, *, method: str, kpi_after: float | None, passed: bool, evidence: list[dict],
           notes: str = "") -> VerificationResult:
    ctx.require("feedback.verify")
    c = _lock(ctx, case_id)
    if c.status != "VERIFY_PENDING":
        raise InvalidTransition("Hồ sơ chưa ở bước kiểm chứng")
    ev = _validate_evidence(evidence)
    if not ev:
        raise ValidationFailed("Kết quả kiểm chứng phải có bằng chứng", code="EVIDENCE_REQUIRED")
    if not method.strip():
        raise ValidationFailed("Thiếu phương pháp kiểm chứng")
    if passed and c.kpi_target is not None and kpi_after is not None and c.kpi_before is not None:
        improving_up = c.kpi_target >= c.kpi_before
        if (improving_up and kpi_after < c.kpi_target) or (not improving_up and kpi_after > c.kpi_target):
            raise ValidationFailed(f"KPI sau ({kpi_after}) chưa đạt mục tiêu ({c.kpi_target}) — không thể kết luận đạt",
                                   code="KPI_NOT_MET")
    vr = VerificationResult(feedback_case_id=c.id, method=method, kpi_before=c.kpi_before, kpi_after=kpi_after, passed=passed,
                            evidence=ev, notes=notes, verified_by=ctx.actor.user_uuid)
    ctx.db.add(vr)
    c.kpi_after = kpi_after
    c.evidence = [*(c.evidence or []), *ev]
    if passed:
        _move(ctx, c, "VERIFIED", f"Kiểm chứng ĐẠT: {method}")
    else:
        c.reopen_count += 1
        _move(ctx, c, "REOPENED", f"Kiểm chứng KHÔNG ĐẠT: {notes or method}")
    return vr


def reopen_restart(ctx: Ctx, case_id, target: str, note: str = "") -> FeedbackCase:
    ctx.require("feedback.manage")
    c = _lock(ctx, case_id)
    if c.status != "REOPENED":
        raise InvalidTransition("Hồ sơ không ở trạng thái REOPENED")
    if target not in ("RCA_PENDING", "IN_PROGRESS"):
        raise ValidationFailed("Chỉ quay lại RCA_PENDING hoặc IN_PROGRESS")
    if target == "IN_PROGRESS":
        for a in ctx.db.scalars(select(CAPAAction).where(CAPAAction.feedback_case_id == c.id, CAPAAction.status == "DONE")):
            a.status = "IN_PROGRESS"
    _move(ctx, c, target, note or "Mở lại xử lý")
    return c


def standardize(ctx: Ctx, case_id, *, note: str, create_lesson: bool = True, lesson: dict | None = None) -> dict:
    ctx.require("feedback.close")
    c = _lock(ctx, case_id)
    if c.status != "VERIFIED":
        raise InvalidTransition("Chỉ chuẩn hoá sau khi kiểm chứng đạt")
    if not note.strip():
        raise ValidationFailed("Mô tả nội dung chuẩn hoá (SOP/prompt/checklist được cập nhật)")
    c.standardization_note = note
    _move(ctx, c, "STANDARDIZED", note)
    out = {"case": c, "lesson": None}
    if create_lesson:
        from app.modules.learning.service import draft_from_case

        out["lesson"] = draft_from_case(ctx, c, lesson or {})
    return out


def close_case(ctx: Ctx, case_id, note: str = "") -> FeedbackCase:
    ctx.require("feedback.close")
    c = _lock(ctx, case_id)
    if c.status != "STANDARDIZED":
        raise InvalidTransition("Chỉ đóng hồ sơ sau khi chuẩn hoá")
    if not c.evidence:
        raise ValidationFailed("Không đóng hồ sơ khi thiếu bằng chứng", code="EVIDENCE_REQUIRED")
    ok = ctx.db.scalar(select(VerificationResult.id).where(VerificationResult.feedback_case_id == c.id, VerificationResult.passed))
    if not ok:
        raise ValidationFailed("Không đóng hồ sơ khi chưa có kết quả kiểm chứng đạt", code="VERIFICATION_REQUIRED")
    c.closed_at = _now()
    _move(ctx, c, "CLOSED", note or "Đóng hồ sơ")
    return c


def list_cases(ctx: Ctx, *, status=None, priority=None, source=None, project_id=None, category=None, q=None, page=1,
               page_size=50):
    stmt = select(FeedbackCase).where(FeedbackCase.data_mode == ctx.mode)
    if status:
        stmt = stmt.where(FeedbackCase.status.in_(status.split(",")))
    if priority:
        stmt = stmt.where(FeedbackCase.priority.in_(priority.split(",")))
    if source:
        stmt = stmt.where(FeedbackCase.source == source)
    if project_id:
        stmt = stmt.where(FeedbackCase.project_id == project_id)
    if category:
        stmt = stmt.where(FeedbackCase.category == category)
    if q:
        stmt = stmt.where(or_(FeedbackCase.title.ilike(f"%{q}%"), FeedbackCase.code.ilike(f"%{q}%")))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = ctx.db.scalars(stmt.order_by(FeedbackCase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def case_detail(ctx: Ctx, case_id) -> dict:
    c = get_case(ctx, case_id)
    return {
        "case": c,
        "rca": ctx.db.scalars(select(RootCauseAnalysis).where(RootCauseAnalysis.feedback_case_id == c.id)
                              .order_by(RootCauseAnalysis.created_at.desc())).all(),
        "capa": ctx.db.scalars(select(CAPAAction).where(CAPAAction.feedback_case_id == c.id).order_by(CAPAAction.created_at)).all(),
        "verifications": ctx.db.scalars(select(VerificationResult).where(VerificationResult.feedback_case_id == c.id)
                                        .order_by(VerificationResult.created_at)).all(),
        "events": c.events,
        "overdue": bool(c.deadline and c.deadline < _now() and c.status not in ("CLOSED", "VERIFIED", "STANDARDIZED")),
    }


def stats(ctx: Ctx) -> dict:
    rows = ctx.db.execute(select(FeedbackCase.status, func.count()).where(FeedbackCase.data_mode == ctx.mode)
                          .group_by(FeedbackCase.status)).all()
    by_status = {s: n for s, n in rows}
    verified = sum(by_status.get(s, 0) for s in ("VERIFIED", "STANDARDIZED", "CLOSED"))
    with_capa = sum(by_status.get(s, 0) for s in ("ACTION_APPROVED", "IN_PROGRESS", "VERIFY_PENDING", "VERIFIED",
                                                  "STANDARDIZED", "CLOSED", "REOPENED"))
    overdue = ctx.db.scalar(select(func.count()).select_from(FeedbackCase).where(
        FeedbackCase.data_mode == ctx.mode, FeedbackCase.deadline < _now(),
        FeedbackCase.status.notin_(["VERIFIED", "STANDARDIZED", "CLOSED"]))) or 0
    return {"by_status": by_status, "total": sum(by_status.values()), "capa_verified_rate": round(verified / with_capa * 100, 1) if with_capa else None,
            "overdue": overdue, "formula": "Tỷ lệ CAPA được xác minh = (VERIFIED+STANDARDIZED+CLOSED) / số hồ sơ đã duyệt CAPA"}


def new_id() -> uuid.UUID:
    return uuid.uuid4()
