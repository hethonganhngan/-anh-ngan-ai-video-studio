"""B07 — Quality Control Engine."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.agents.runner import run_agent
from app.core import audit
from app.core.context import Ctx
from app.core.errors import InvalidTransition, NotFound, ValidationFailed
from app.media.models import Asset
from app.modules.administration.service import get_setting, notify
from app.modules.projects.models import BrandProfile, Project
from app.modules.projects.service import get_project, lock_project
from app.modules.quality.compliance import scan
from app.modules.quality.criteria import BY_KEY, CRITERIA, KEYS
from app.modules.quality.models import Approval, QCFinding, QCReview
from app.modules.rendering.models import Render
from app.modules.scripts.models import Scene, Script, ScriptVersion
from app.workflows import state_machine as sm


def _now():
    return datetime.now(timezone.utc)


def _asset_path(a: Asset, cleanup: list) -> str:
    from app.modules.rendering.service import _local

    return _local(a, cleanup)


# ---------------- Scene QC (A07) ----------------
def _scene_checks(ctx: Ctx, p: Project, scene: Scene) -> tuple[list[dict], dict]:
    from app.media.storage import safe_remove
    from app.modules.rendering.ffmpeg import measure

    a = ctx.db.get(Asset, scene.selected_asset_id) if scene.selected_asset_id else None
    findings: list[dict] = []
    if a is None or a.deleted_at:
        return [{"criterion": "visual", "severity": "CRITICAL", "description": "Cảnh chưa có video"}], {}
    info = a.media_info or {}
    w, h, d = a.width or 0, a.height or 0, a.duration_sec or 0
    if w and h and abs(w / h - 9 / 16) > 0.03:
        findings.append({"criterion": "visual", "severity": "MAJOR", "description": f"Tỉ lệ {w}x{h} không phải 9:16"})
    from app.core.config import get_settings

    min_h = int(get_settings().output_height * 2 / 3)  # 1920 → 1280
    if h and h < min_h:
        findings.append({"criterion": "visual", "severity": "MAJOR", "description": f"Độ phân giải {w}x{h} quá thấp"})
    if abs(d - scene.duration_sec) > 1.0:
        findings.append({"criterion": "script", "severity": "MINOR", "description": f"Thời lượng {d:.1f}s khác mục tiêu {scene.duration_sec}s"})
    if not info.get("has_audio"):
        findings.append({"criterion": "audio", "severity": "MINOR", "description": "Cảnh không có âm thanh"})
    cleanup: list = []
    try:
        m = measure(_asset_path(a, cleanup))
    finally:
        for f in cleanup:
            safe_remove(f)
    if m.get("black_seconds", 0) > max(1.0, d * 0.25):
        findings.append({"criterion": "visual", "severity": "MAJOR", "description": f"Khung đen {m['black_seconds']}s"})
    return findings, {**info, **m}


def run_scene_qc(ctx: Ctx, p: Project) -> dict:
    scenes = ctx.db.scalars(select(Scene).where(Scene.project_id == p.id).order_by(Scene.order_index)).all()

    def work(_llm, _actx):
        results = []
        for s in scenes:
            if s.status == "QC_PASSED":
                results.append({"scene": s.order_index, "passed": True, "skipped": True})
                continue
            findings, checks = _scene_checks(ctx, p, s)
            blocking = [f for f in findings if f["severity"] in ("CRITICAL", "MAJOR")]
            review = QCReview(project_id=p.id, scene_id=s.id, review_type="SCENE", reviewer_type="AGENT",
                              automated_checks=checks, result="FAIL" if blocking else "PASS",
                              has_critical=any(f["severity"] == "CRITICAL" for f in findings), data_mode=ctx.mode,
                              notes="A07 kiểm tra kỹ thuật tự động; nhân vật/khẩu hình cần người xem")
            ctx.db.add(review)
            ctx.db.flush()
            for f in findings:
                ctx.db.add(QCFinding(qc_review_id=review.id, project_id=p.id, scene_id=s.id, criterion=f["criterion"],
                                     severity=f["severity"], description=f["description"], evidence={"checks": checks}))
            s.status = "QC_FAILED" if blocking else "QC_PASSED"
            results.append({"scene": s.order_index, "passed": not blocking, "findings": findings})
        return {"result": results, "count": len(results)}, None

    run = run_agent(ctx, "A07", "qc.scene_check", work, project=p, input_ref={"project": p.code})
    results = run.output["result"]
    all_passed = all(r["passed"] for r in results)
    if not all_passed:
        notify(ctx.db, ctx.mode, f"QC cảnh chưa đạt: {p.code}", f"{sum(not r['passed'] for r in results)} cảnh cần tạo lại",
               level="WARNING", category="QC", link=f"/production?project={p.id}")
    return {"all_passed": all_passed, "results": results}


def human_scene_review(ctx: Ctx, scene_id, passed: bool, notes: str, severity: str | None = None,
                       criterion: str = "character") -> QCReview:
    ctx.require("qc.review")
    scene = ctx.db.get(Scene, scene_id)
    if scene is None or scene.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy cảnh")
    p = lock_project(ctx, scene.project_id)
    if p.status not in ("SCENE_QC", "FINAL_QC", "NEEDS_MANUAL_ACTION"):
        raise InvalidTransition(f"Không QC cảnh ở trạng thái {p.status}")
    if not passed and not notes.strip():
        raise ValidationFailed("Cần mô tả lỗi khi đánh giá không đạt")
    if criterion not in KEYS:
        raise ValidationFailed("Tiêu chí không hợp lệ")
    review = QCReview(project_id=p.id, scene_id=scene.id, review_type="SCENE", reviewer_type="HUMAN",
                      reviewer_id=ctx.actor.user_uuid, result="PASS" if passed else "FAIL", notes=notes, data_mode=ctx.mode)
    ctx.db.add(review)
    ctx.db.flush()
    if not passed:
        ctx.db.add(QCFinding(qc_review_id=review.id, project_id=p.id, scene_id=scene.id, criterion=criterion,
                             severity=severity or "MAJOR", description=notes, evidence={"reviewer": ctx.actor.label}))
        scene.status = "QC_FAILED"
    else:
        scene.status = "QC_PASSED"
    audit.record(ctx, "qc.scene_review", "scene", scene.id, after={"passed": passed, "notes": notes})
    return review


# ---------------- Final QC ----------------
def _script_text(ctx: Ctx, p: Project) -> tuple[str, ScriptVersion | None]:
    script = ctx.db.scalar(select(Script).where(Script.project_id == p.id))
    v = ctx.db.get(ScriptVersion, script.approved_version_id or script.current_version_id) if script else None
    if v is None:
        return "", None
    lines = " ".join(d.get("text", "") for s in v.scenes for d in s.get("dialogue", []))
    return f"{v.hook} {v.body} {v.cta} {lines}", v


def run_final_auto_qc(ctx: Ctx, p: Project, render: Render) -> QCReview:
    """A07: đo kỹ thuật + tuân thủ; gợi ý điểm. Tiêu chí MANUAL để trống → bắt buộc người chấm."""
    from app.media.storage import safe_remove
    from app.modules.rendering.ffmpeg import measure
    from app.modules.scripts.validation import validate_scenes

    def work(_llm, _actx):
        cleanup: list = []
        try:
            m = measure(_asset_path(ctx.db.get(Asset, render.video_asset_id), cleanup))
        finally:
            for f in cleanup:
                safe_remove(f)
        bp = ctx.db.scalar(select(BrandProfile).where(BrandProfile.channel_id == p.channel_id))
        text, v = _script_text(ctx, p)
        compliance = [f.to_dict() for f in scan(text, bp.forbidden_terms if bp else [])]
        findings, scores = [], {}
        # Hình ảnh (AUTO)
        vis = 10
        from app.core.config import get_settings

        tw, th = get_settings().output_width, get_settings().output_height
        if (render.width, render.height) != (tw, th):
            vis -= 4
            findings.append(("visual", "MAJOR", f"Độ phân giải {render.width}x{render.height} ≠ {tw}x{th}"))
        if (render.probe or {}).get("fps") and abs(render.probe["fps"] - 30) > 0.5:
            vis -= 1
        if m.get("black_seconds", 0) > 0.5:
            vis -= min(5, int(m["black_seconds"]))
            findings.append(("visual", "MAJOR" if m["black_seconds"] > 2 else "MINOR", f"Khung đen {m['black_seconds']}s"))
        scores["visual"] = {"score": max(0, vis), "method": "AUTO", "evidence": {"w": render.width, "h": render.height, **m}}
        # Âm thanh (AUTO)
        aud = 10
        lufs = m.get("integrated_lufs")
        if not (render.probe or {}).get("has_audio"):
            aud = 0
            findings.append(("audio", "CRITICAL", "Video không có âm thanh"))
        elif lufs is None or lufs < -24 or lufs > -9:
            aud -= 3
            findings.append(("audio", "MAJOR", f"Độ ồn {lufs} LUFS ngoài khoảng -24..-9"))
        elif lufs < -20 or lufs > -12:
            aud -= 1
        if m.get("longest_silence", 0) > 3:
            aud -= 2
            findings.append(("audio", "MINOR", f"Khoảng lặng dài {m['longest_silence']}s"))
        scores["audio"] = {"score": max(0, aud), "method": "AUTO", "evidence": {"lufs": lufs, "silence": m.get("longest_silence")}}
        # Hook (ASSISTED)
        hook_words = len((v.hook if v else "").split())
        scores["hook"] = {"score": 10 if v and 3 <= hook_words <= 16 else 7, "method": "ASSISTED",
                          "evidence": {"hook": v.hook if v else "", "words": hook_words}}
        # Kịch bản (ASSISTED)
        errs, warns = validate_scenes(v.scenes if v else [])
        scores["script"] = {"score": max(0, 10 - 3 * len(errs) - len(warns)), "method": "ASSISTED",
                            "evidence": {"errors": errs, "warnings": warns}}
        # Thương hiệu (ASSISTED)
        tl = p.timeline or {}
        brand = 10 - (0 if tl.get("logo") else 3) - (0 if (v and v.cta) else 3)
        if not tl.get("logo"):
            findings.append(("brand", "MINOR", "Video chưa gắn logo"))
        scores["brand"] = {"score": max(0, brand), "method": "ASSISTED", "evidence": {"logo": bool(tl.get("logo")), "cta": v.cta if v else ""}}
        # Tuân thủ (ASSISTED)
        crit = [c for c in compliance if c["severity"] == "CRITICAL"]
        scores["compliance"] = {"score": 0 if crit else max(0, 10 - 3 * len(compliance)), "method": "ASSISTED",
                                "evidence": {"findings": compliance}}
        for c in compliance:
            findings.append(("compliance", c["severity"], c["message"] + f" ('{c['match']}')"))
        for k in KEYS:
            scores.setdefault(k, {"score": None, "method": "MANUAL", "evidence": {}})
        return {"result": {"scores": scores, "findings": findings, "measure": m}}, None

    run = run_agent(ctx, "A07", "qc.final_check", work, project=p, input_ref={"render": str(render.id)})
    res = run.output["result"]
    pending = [k for k in KEYS if BY_KEY[k]["method"] != "AUTO"]
    review = QCReview(project_id=p.id, render_id=render.id, review_type="FINAL", reviewer_type="AGENT", scores=res["scores"],
                      total_score=sum(v["score"] or 0 for v in res["scores"].values()), pending_manual=pending,
                      automated_checks=res["measure"], has_critical=any(f[1] == "CRITICAL" for f in res["findings"]),
                      result="NEEDS_MANUAL", notes="Gợi ý của A07 — cần Quality Reviewer chấm xác nhận", data_mode=ctx.mode,
                      agent_execution_id=run.execution.id)
    ctx.db.add(review)
    ctx.db.flush()
    for crit, sev, desc in res["findings"]:
        f = QCFinding(qc_review_id=review.id, project_id=p.id, criterion=crit, severity=sev, description=desc,
                      evidence={"render_id": str(render.id)})
        ctx.db.add(f)
        ctx.db.flush()
        if sev == "CRITICAL":
            from app.modules.feedback.service import create_from_finding

            create_from_finding(ctx, f, auto=True)
    notify(ctx.db, ctx.mode, f"Video chờ QC: {p.code}", f"Render v{render.version_no} cần chấm 10 tiêu chí",
           category="QC", link=f"/quality?project={p.id}")
    return review


def latest_reviews(ctx: Ctx, project_id) -> dict:
    p = get_project(ctx, project_id)
    render = ctx.db.scalar(select(Render).where(Render.project_id == p.id).order_by(Render.version_no.desc()))
    reviews = ctx.db.scalars(select(QCReview).where(QCReview.project_id == p.id).order_by(QCReview.created_at.desc())).all()
    findings = ctx.db.scalars(select(QCFinding).where(QCFinding.project_id == p.id).order_by(QCFinding.created_at.desc())).all()
    approvals = ctx.db.scalars(select(Approval).where(Approval.project_id == p.id).order_by(Approval.created_at.desc())).all()
    agent_final = next((r for r in reviews if r.review_type == "FINAL" and r.reviewer_type == "AGENT"
                        and render and r.render_id == render.id), None)
    return {"project": p, "render": render, "reviews": reviews, "findings": findings, "approvals": approvals,
            "agent_final": agent_final, "criteria": CRITERIA, "policy": get_setting(ctx.db, "qc.policy")}


def blocking_findings(ctx: Ctx, project_id) -> list[QCFinding]:
    sev = get_setting(ctx.db, "qc.policy").get("blocking_severities", ["CRITICAL", "MAJOR"])
    return ctx.db.scalars(select(QCFinding).where(QCFinding.project_id == project_id, QCFinding.status == "OPEN",
                                                  QCFinding.severity.in_(sev))).all()


def submit_final_review(ctx: Ctx, project_id, scores: dict, notes: str, new_findings: list[dict]) -> QCReview:
    ctx.require("qc.review")
    p = lock_project(ctx, project_id)
    if p.status != "FINAL_QC":
        raise InvalidTransition("Chỉ chấm QC tổng thể ở trạng thái FINAL_QC")
    render = ctx.db.scalar(select(Render).where(Render.project_id == p.id).order_by(Render.version_no.desc()))
    if render is None:
        raise ValidationFailed("Chưa có bản render")
    agent = ctx.db.scalar(select(QCReview).where(QCReview.render_id == render.id, QCReview.reviewer_type == "AGENT",
                                                 QCReview.review_type == "FINAL"))
    missing = [k for k in KEYS if k not in scores]
    if missing:
        raise ValidationFailed("Phải chấm đủ 10 tiêu chí", code="QC_INCOMPLETE", details={"missing": missing})
    out = {}
    for k in KEYS:
        item = scores[k]
        sc = item["score"] if isinstance(item, dict) else item
        if not isinstance(sc, (int, float)) or not 0 <= sc <= 10:
            raise ValidationFailed(f"Điểm {BY_KEY[k]['label']} phải từ 0–10")
        if BY_KEY[k]["method"] == "AUTO" and agent and agent.scores.get(k, {}).get("score") is not None \
                and sc > agent.scores[k]["score"]:
            raise ValidationFailed(f"{BY_KEY[k]['label']} là tiêu chí đo tự động: không được chấm cao hơn kết quả đo "
                                   f"({agent.scores[k]['score']})", code="QC_AUTO_OVERRIDE")
        out[k] = {"score": sc, "method": BY_KEY[k]["method"], "note": item.get("note", "") if isinstance(item, dict) else ""}
    review = QCReview(project_id=p.id, render_id=render.id, review_type="FINAL", reviewer_type="HUMAN",
                      reviewer_id=ctx.actor.user_uuid, scores=out, total_score=sum(v["score"] for v in out.values()),
                      notes=notes, data_mode=ctx.mode)
    ctx.db.add(review)
    ctx.db.flush()
    for nf in new_findings or []:
        if nf.get("criterion") not in KEYS or nf.get("severity") not in ("CRITICAL", "MAJOR", "MINOR"):
            raise ValidationFailed("Lỗi QC mới không hợp lệ")
        f = QCFinding(qc_review_id=review.id, project_id=p.id, scene_id=nf.get("scene_id"), criterion=nf["criterion"],
                      severity=nf["severity"], description=nf.get("description", ""), evidence={"reviewer": ctx.actor.label})
        ctx.db.add(f)
    ctx.db.flush()
    policy = get_setting(ctx.db, "qc.policy")
    blocking = blocking_findings(ctx, p.id)
    passed = review.total_score >= policy["min_total"] and not blocking
    review.has_critical = any(f.severity == "CRITICAL" for f in blocking)
    review.result = "PASS" if passed else "FAIL"
    render.status = "QC_PASSED" if passed else "QC_FAILED"
    audit.record(ctx, "qc.final_review", "project", p.id,
                 after={"total": review.total_score, "result": review.result, "blocking": len(blocking)})
    if passed:
        sm.transition(ctx, p, "APPROVAL_PENDING", note=f"QC đạt {review.total_score}/100")
        notify(ctx.db, ctx.mode, f"Chờ phê duyệt: {p.code}", f"QC {review.total_score}/100", category="APPROVAL",
               link=f"/quality?project={p.id}")
    else:
        reasons = []
        if review.total_score < policy["min_total"]:
            reasons.append(f"điểm {review.total_score} < {policy['min_total']}")
        if blocking:
            reasons.append(f"{len(blocking)} lỗi nghiêm trọng chưa xử lý")
        review.notes = (notes + " | KHÔNG ĐẠT: " + ", ".join(reasons)).strip(" |")
        notify(ctx.db, ctx.mode, f"QC không đạt: {p.code}", ", ".join(reasons), level="WARNING", category="QC",
               link=f"/quality?project={p.id}")
    return review


def resolve_finding(ctx: Ctx, finding_id, action: str, note: str) -> QCFinding:
    ctx.require("qc.waive")
    f = ctx.db.get(QCFinding, finding_id)
    if f is None:
        raise NotFound("Không tìm thấy lỗi QC")
    get_project(ctx, f.project_id)
    if f.status != "OPEN":
        raise ValidationFailed("Lỗi đã được xử lý")
    if not note.strip():
        raise ValidationFailed("Cần ghi chú/bằng chứng khi xử lý lỗi")
    if action == "WAIVE" and f.severity == "CRITICAL":
        raise ValidationFailed("Không được miễn lỗi CRITICAL — phải khắc phục", code="CANNOT_WAIVE_CRITICAL")
    if action not in ("RESOLVE", "WAIVE"):
        raise ValidationFailed("Hành động không hợp lệ")
    f.status = "RESOLVED" if action == "RESOLVE" else "WAIVED"
    f.resolved_by = ctx.actor.user_uuid
    f.resolved_at = _now()
    f.resolution_note = note
    audit.record(ctx, f"qc.finding_{action.lower()}", "qc_finding", f.id, after={"note": note})
    return f


def approve(ctx: Ctx, project_id, decision: str, comment: str) -> Approval:
    """Phê duyệt phát hành — chỉ người có quyền project.approve; yêu cầu QC HUMAN đạt trên bản render mới nhất."""
    ctx.require("project.approve")
    p = lock_project(ctx, project_id)
    if p.status != "APPROVAL_PENDING":
        raise InvalidTransition("Dự án chưa ở bước chờ phê duyệt")
    if decision not in ("APPROVED", "REJECTED"):
        raise ValidationFailed("Quyết định không hợp lệ")
    render = ctx.db.scalar(select(Render).where(Render.project_id == p.id).order_by(Render.version_no.desc()))
    human = ctx.db.scalar(select(QCReview).where(QCReview.render_id == render.id, QCReview.reviewer_type == "HUMAN",
                                                 QCReview.review_type == "FINAL").order_by(QCReview.created_at.desc()))
    if decision == "APPROVED":
        policy = get_setting(ctx.db, "qc.policy")
        if human is None or human.result != "PASS" or human.total_score < policy["min_total"]:
            raise ValidationFailed("Chưa có kết quả QC đạt chuẩn cho bản render mới nhất", code="QC_NOT_PASSED")
        if blocking_findings(ctx, p.id):
            raise ValidationFailed("Còn lỗi nghiêm trọng chưa xử lý", code="OPEN_CRITICAL_FINDINGS")
    elif not comment.strip():
        raise ValidationFailed("Cần nêu lý do từ chối")
    ap = Approval(project_id=p.id, render_id=render.id, qc_review_id=human.id if human else None,
                  approver_id=ctx.actor.user_uuid, decision=decision, comment=comment, data_mode=ctx.mode)
    ctx.db.add(ap)
    if decision == "APPROVED":
        p.approved_by = ctx.actor.user_uuid
        p.approved_at = _now()
        render.status = "APPROVED"
        sm.transition(ctx, p, "APPROVED", note=f"Phê duyệt bởi {ctx.actor.label}. {comment}".strip())
    else:
        render.status = "QC_FAILED"
        sm.transition(ctx, p, "FINAL_QC", note=f"Từ chối: {comment}")
    audit.record(ctx, "project.approval", "project", p.id, after={"decision": decision, "comment": comment,
                                                                   "render": render.version_no})
    return ap
