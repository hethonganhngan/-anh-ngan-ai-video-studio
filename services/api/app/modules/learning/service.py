"""B09 — AI Lessons Learned Engine. Bài học chỉ đi vào cấu hình chuẩn sau khi được duyệt; có rollback."""
from datetime import datetime, timezone

from sqlalchemy import String, cast, func, or_, select

from app.agents.runner import run_agent
from app.core import audit
from app.core.codes import next_code
from app.core.context import Ctx
from app.core.errors import Conflict, InvalidTransition, NotFound, ValidationFailed
from app.modules.feedback.models import CAPAAction, FeedbackCase, RootCauseAnalysis, VerificationResult
from app.modules.learning.models import LessonLearned
from app.modules.prompts import service as prompts
from app.modules.prompts.models import PromptTemplate, PromptVersion

LESSON_TYPES = {"RESOLVED_ERROR", "FAILED_PROMPT", "EFFECTIVE_PROMPT", "GOOD_VOICE_LOCK", "GOOD_CHARACTER_LOCK", "ROOT_CAUSE",
                "EFFECTIVE_CAPA"}
EDITABLE = {"DRAFT", "PENDING_APPROVAL", "REJECTED"}
FIELDS = ["lesson_type", "title", "lesson", "root_cause", "capa_summary", "verification_summary", "channel_id",
          "character_id", "error_category", "provider_code", "prompt_example", "proposed_change", "tags"]


def _now():
    return datetime.now(timezone.utc)


def get_lesson(ctx: Ctx, lid) -> LessonLearned:
    x = ctx.db.get(LessonLearned, lid)
    if x is None or x.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy bài học")
    return x


def _check_change(ctx: Ctx, change: dict) -> dict:
    if not change:
        return {}
    code = change.get("template_code")
    if not code:
        raise ValidationFailed("proposed_change cần template_code")
    prompts.get_template(ctx, code)
    if not (change.get("append_negative") or change.get("append_rule")):
        raise ValidationFailed("proposed_change cần append_negative hoặc append_rule")
    return {"template_code": code, "append_negative": (change.get("append_negative") or "").strip(),
            "append_rule": (change.get("append_rule") or "").strip()}


def create_lesson(ctx: Ctx, data: dict, *, feedback_case_id=None, actor_check=True) -> LessonLearned:
    if actor_check:
        ctx.require("lesson.create")
    if data.get("lesson_type") not in LESSON_TYPES:
        raise ValidationFailed("Loại bài học không hợp lệ")
    if not (data.get("title") or "").strip() or not (data.get("lesson") or "").strip():
        raise ValidationFailed("Bài học cần tiêu đề và nội dung")
    vals = {k: data.get(k) for k in FIELDS if data.get(k) is not None}
    vals["proposed_change"] = _check_change(ctx, data.get("proposed_change") or {})
    x = LessonLearned(code=next_code(ctx.db, LessonLearned, "LL"), feedback_case_id=feedback_case_id, status="DRAFT",
                      created_by=ctx.actor.user_uuid, data_mode=ctx.mode, **vals)
    ctx.db.add(x)
    ctx.db.flush()
    audit.record(ctx, "lesson.create", "lesson", x.id, after={"code": x.code, "type": x.lesson_type})
    return x


def draft_from_case(ctx: Ctx, case: FeedbackCase, overrides: dict) -> LessonLearned:
    """A09: soạn nháp bài học từ hồ sơ đã kiểm chứng (không tự áp dụng)."""
    rca = ctx.db.scalar(select(RootCauseAnalysis).where(RootCauseAnalysis.feedback_case_id == case.id, RootCauseAnalysis.is_current))
    capas = ctx.db.scalars(select(CAPAAction).where(CAPAAction.feedback_case_id == case.id, CAPAAction.status == "DONE")).all()
    vr = ctx.db.scalar(select(VerificationResult).where(VerificationResult.feedback_case_id == case.id, VerificationResult.passed)
                       .order_by(VerificationResult.created_at.desc()))
    if vr is None:
        raise ValidationFailed("Chỉ soạn bài học từ hồ sơ đã kiểm chứng đạt", code="VERIFICATION_REQUIRED")
    capa_text = "; ".join(f"[{a.action_type}] {a.description}" for a in capas)
    kpi = f"KPI {case.kpi_name}: {case.kpi_before} → {vr.kpi_after}" if case.kpi_name else ""

    def work(llm, _actx):
        res = llm.complete_json(system="A09 Lesson", prompt=f"{case.code} {case.title}", schema={"type": "object"},
                                mock_fn=lambda: {"title": f"Bài học: {case.title[:200]}",
                                                 "lesson": f"Khi gặp '{case.title}', nguyên nhân gốc là: "
                                                           f"{rca.root_cause if rca else 'chưa xác định'}. "
                                                           f"Áp dụng: {capa_text}. {kpi}".strip()})
        return res.data, res

    run = run_agent(ctx, "A09", "lesson.draft", work, needs_llm=True, input_ref={"case": case.code})
    lesson_type = overrides.get("lesson_type") or ("FAILED_PROMPT" if case.category == "PROMPT" else "RESOLVED_ERROR")
    data = {"lesson_type": lesson_type, "title": overrides.get("title") or run.output["title"],
            "lesson": overrides.get("lesson") or run.output["lesson"], "root_cause": rca.root_cause if rca else "",
            "capa_summary": capa_text, "verification_summary": f"{vr.method}. {kpi}".strip(),
            "channel_id": case.channel_id, "character_id": case.character_id, "error_category": case.category,
            "provider_code": case.provider_code, "proposed_change": overrides.get("proposed_change") or {},
            "tags": overrides.get("tags") or [case.category.lower(), case.source.lower()]}
    return create_lesson(ctx, data, feedback_case_id=case.id, actor_check=False)


def update_lesson(ctx: Ctx, lid, data: dict) -> LessonLearned:
    ctx.require("lesson.create")
    x = get_lesson(ctx, lid)
    if x.status not in EDITABLE:
        raise InvalidTransition("Bài học đã duyệt/áp dụng không được sửa — tạo bài học mới")
    if "proposed_change" in data:
        data["proposed_change"] = _check_change(ctx, data["proposed_change"] or {})
    snapshot = {k: getattr(x, k) for k in FIELDS}
    x.history = [*(x.history or []), {"version": x.version_no, "at": _now().isoformat(), "data": audit._jsonable(snapshot)}]
    for k, v in data.items():
        if k in FIELDS:
            setattr(x, k, v)
    x.version_no += 1
    x.status = "DRAFT"
    audit.record(ctx, "lesson.update", "lesson", x.id, after={"version": x.version_no})
    return x


def submit_lesson(ctx: Ctx, lid) -> LessonLearned:
    ctx.require("lesson.create")
    x = get_lesson(ctx, lid)
    if x.status not in ("DRAFT", "REJECTED"):
        raise InvalidTransition("Chỉ gửi duyệt bài học nháp")
    x.status = "PENDING_APPROVAL"
    audit.record(ctx, "lesson.submit", "lesson", x.id)
    return x


def review_lesson(ctx: Ctx, lid, approve: bool, comment: str = "") -> LessonLearned:
    ctx.require("lesson.approve")
    x = get_lesson(ctx, lid)
    if x.status != "PENDING_APPROVAL":
        raise InvalidTransition("Bài học chưa ở trạng thái chờ duyệt")
    if approve and x.feedback_case_id:
        case = ctx.db.get(FeedbackCase, x.feedback_case_id)
        if case.status not in ("VERIFIED", "STANDARDIZED", "CLOSED"):
            raise ValidationFailed("Hồ sơ phản hồi gốc chưa được kiểm chứng", code="VERIFICATION_REQUIRED")
    if not approve and not comment.strip():
        raise ValidationFailed("Cần lý do từ chối")
    x.status = "APPROVED" if approve else "REJECTED"
    if approve:
        x.approved_by = ctx.actor.user_uuid
        x.approved_at = _now()
    x.history = [*(x.history or []), {"version": x.version_no, "at": _now().isoformat(),
                                      "review": "APPROVED" if approve else "REJECTED", "comment": comment}]
    audit.record(ctx, "lesson.review", "lesson", x.id, after={"approved": approve, "comment": comment})
    return x


def apply_lesson(ctx: Ctx, lid) -> PromptVersion:
    """Áp dụng vào prompt chuẩn: tạo phiên bản prompt mới (bất biến) và kích hoạt cho chế độ hiện hành."""
    ctx.require("lesson.apply")
    x = get_lesson(ctx, lid)
    if x.status != "APPROVED":
        raise InvalidTransition("Chỉ áp dụng bài học đã được duyệt", code="LESSON_NOT_APPROVED")
    ch = x.proposed_change or {}
    if not ch.get("template_code"):
        raise ValidationFailed("Bài học không có thay đổi cấu hình để áp dụng")
    tpl = prompts.get_template(ctx, ch["template_code"])
    current = prompts.active_version(ctx, tpl)
    negative = current.negative_prompt
    if ch.get("append_negative") and ch["append_negative"] not in negative:
        negative = f"{negative}, {ch['append_negative']}".strip(", ")
    rules = list(current.rules or [])
    if ch.get("append_rule") and ch["append_rule"] not in rules:
        rules.append(ch["append_rule"])
    v = prompts.create_version(ctx, tpl.id, content=current.content, negative_prompt=negative, rules=rules,
                               change_note=f"Áp dụng {x.code}: {x.title[:150]}", source_lesson_id=x.id, actor_check=False)
    prompts.approve_and_activate(ctx, v.id, actor_check=False)
    x.previous_prompt_version_id = current.id
    x.applied_prompt_version_id = v.id
    x.applied_at = _now()
    x.status = "APPLIED"
    audit.record(ctx, "lesson.apply", "lesson", x.id, after={"template": tpl.code, "from": current.version_no, "to": v.version_no})
    return v


def rollback_lesson(ctx: Ctx, lid, reason: str) -> LessonLearned:
    ctx.require("lesson.apply")
    x = get_lesson(ctx, lid)
    if x.status != "APPLIED":
        raise InvalidTransition("Bài học chưa được áp dụng")
    if not reason.strip():
        raise ValidationFailed("Cần lý do rollback")
    v = ctx.db.get(PromptVersion, x.applied_prompt_version_id)
    tpl = ctx.db.get(PromptTemplate, v.template_id)
    active = prompts.active_version(ctx, tpl)
    if active.id != v.id:
        raise Conflict(f"Prompt {tpl.code} đã có phiên bản mới hơn (v{active.version_no}). Rollback bài học mới hơn trước.",
                       code="ROLLBACK_CONFLICT")
    prompts.set_active_version(ctx, tpl, x.previous_prompt_version_id)
    v.status = "RETIRED"
    x.status = "ROLLED_BACK"
    x.rolled_back_at = _now()
    x.history = [*(x.history or []), {"at": _now().isoformat(), "rollback": reason}]
    audit.record(ctx, "lesson.rollback", "lesson", x.id, after={"template": tpl.code, "reason": reason})
    return x


def search(ctx: Ctx, *, q=None, channel_id=None, character_id=None, error_category=None, provider_code=None,
           lesson_type=None, status=None, page=1, page_size=50):
    stmt = select(LessonLearned).where(LessonLearned.data_mode == ctx.mode)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(LessonLearned.title.ilike(like), LessonLearned.lesson.ilike(like),
                              LessonLearned.root_cause.ilike(like), cast(LessonLearned.tags, String).ilike(like),
                              LessonLearned.code.ilike(like)))
    for col, val in ((LessonLearned.channel_id, channel_id), (LessonLearned.character_id, character_id),
                     (LessonLearned.error_category, error_category), (LessonLearned.provider_code, provider_code),
                     (LessonLearned.lesson_type, lesson_type)):
        if val:
            stmt = stmt.where(col == val)
    if status:
        stmt = stmt.where(LessonLearned.status.in_(status.split(",")))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = ctx.db.scalars(stmt.order_by(LessonLearned.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total


def relevant_for_project(ctx: Ctx, project) -> list[LessonLearned]:
    """A09 lesson.search: bài học đã duyệt/áp dụng liên quan kênh & nhà cung cấp của dự án."""
    stmt = select(LessonLearned).where(LessonLearned.data_mode == ctx.mode, LessonLearned.status.in_(["APPROVED", "APPLIED"]),
                                       or_(LessonLearned.channel_id == project.channel_id, LessonLearned.channel_id.is_(None),
                                           LessonLearned.provider_code == project.video_provider_code))
    return ctx.db.scalars(stmt.order_by(LessonLearned.created_at.desc()).limit(10)).all()
