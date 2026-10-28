"""B11 — Analytics Engine & Dashboard CEO. Mọi KPI là phép tính xác định (không dùng LLM) và kèm công thức + nguồn."""
import csv
import io
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.agents.runner import run_agent
from app.core import audit
from app.core.context import Ctx
from app.core.errors import ValidationFailed
from app.modules.administration.models import BudgetLimit, CostRecord
from app.modules.administration.service import spent
from app.modules.analytics.models import AnalyticsSnapshot
from app.modules.feedback.models import FeedbackCase
from app.modules.generation.models import GenerationJob
from app.modules.projects.models import Project
from app.modules.publishing.models import Publication
from app.modules.publishing.service import get_pub
from app.modules.quality.models import QCReview
from app.workflows import state_machine as sm

METRICS = ["views", "likes", "comments", "shares", "saves", "retention_rate", "avg_watch_sec", "conversions"]
IN_PRODUCTION = ["SCRIPT_GENERATING", "SCRIPT_REVIEW", "STORYBOARD_READY", "ASSET_VALIDATION", "GENERATION_QUEUED",
                 "GENERATING", "SCENE_QC", "RENDERING", "FINAL_QC", "RETRY_PENDING", "NEEDS_MANUAL_ACTION"]
PENDING_APPROVAL = ["APPROVAL_PENDING"]
COMPLETED = ["APPROVED", "PUBLISH_QUEUED", "PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW"]
PUBLISHED = ["PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW"]


def _now():
    return datetime.now(timezone.utc)


def add_snapshot(ctx: Ctx, pub_id, data: dict, source: str = "MANUAL") -> AnalyticsSnapshot:
    ctx.require("analytics.enter")
    pub = get_pub(ctx, pub_id)
    if pub.status != "PUBLISHED":
        raise ValidationFailed("Chỉ nhập số liệu cho bài đã đăng")
    for k in ("views", "likes", "comments", "shares", "saves", "conversions"):
        if data.get(k) is not None and int(data[k]) < 0:
            raise ValidationFailed(f"{k} không được âm")
    if data.get("retention_rate") is not None and not 0 <= float(data["retention_rate"]) <= 100:
        raise ValidationFailed("Tỷ lệ giữ chân phải 0–100%")
    if data.get("likes", 0) and data.get("views") is not None and int(data["likes"]) > int(data["views"]) * 1.0 + 1:
        raise ValidationFailed("Lượt thích lớn hơn lượt xem — kiểm tra lại số liệu")
    prev = ctx.db.scalar(select(AnalyticsSnapshot).where(AnalyticsSnapshot.publication_id == pub.id)
                         .order_by(AnalyticsSnapshot.captured_at.desc()))
    captured = data.get("captured_at") or _now()
    if prev and captured >= prev.captured_at and int(data.get("views") or 0) < prev.views:
        raise ValidationFailed(f"Lượt xem tích luỹ giảm ({prev.views} → {data.get('views')}) — số liệu không hợp lệ",
                               code="METRIC_DECREASED")
    snap = AnalyticsSnapshot(publication_id=pub.id, project_id=pub.project_id, captured_at=captured, source=source,
                             entered_by=ctx.actor.user_uuid, data_mode=ctx.mode,
                             **{k: data.get(k) for k in METRICS if data.get(k) is not None})
    ctx.db.add(snap)
    p = ctx.db.get(Project, pub.project_id)
    if p.status == "PUBLISHED":
        sm.transition(ctx, p, "ANALYTICS_COLLECTION", note="Bắt đầu thu thập số liệu")
    audit.record(ctx, "analytics.snapshot", "publication", pub.id, after={"views": snap.views, "source": source})
    return snap


def import_csv(ctx: Ctx, content: bytes) -> dict:
    """CSV cột: post_url hoặc publication_id, captured_at(ISO), views, likes, comments, shares, saves, retention_rate,
    avg_watch_sec, conversions."""
    ctx.require("analytics.enter")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationFailed("CSV phải mã hoá UTF-8")
    reader = csv.DictReader(io.StringIO(text))
    ok, errors = 0, []
    for i, row in enumerate(reader, start=2):
        try:
            pub = None
            if row.get("publication_id"):
                pub = get_pub(ctx, row["publication_id"].strip())
            elif row.get("post_url"):
                pub = ctx.db.scalar(select(Publication).where(Publication.post_url == row["post_url"].strip(),
                                                              Publication.data_mode == ctx.mode))
            if pub is None:
                raise ValidationFailed("Không tìm thấy bài đăng")
            data = {}
            for k in METRICS:
                v = (row.get(k) or "").strip()
                if v != "":
                    data[k] = float(v) if k in ("retention_rate", "avg_watch_sec") else int(float(v))
            if row.get("captured_at"):
                dt = datetime.fromisoformat(row["captured_at"].strip())
                data["captured_at"] = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            with ctx.db.begin_nested():
                add_snapshot(ctx, pub.id, data, source="CSV")
            ok += 1
        except (ValidationFailed, ValueError) as e:
            errors.append({"row": i, "error": getattr(e, "message", str(e))})
    return {"imported": ok, "errors": errors}


def _latest_snapshots(ctx: Ctx, pub_ids: list) -> dict:
    if not pub_ids:
        return {}
    sub = (select(AnalyticsSnapshot.publication_id, func.max(AnalyticsSnapshot.captured_at).label("m"))
           .where(AnalyticsSnapshot.publication_id.in_(pub_ids)).group_by(AnalyticsSnapshot.publication_id).subquery())
    rows = ctx.db.scalars(select(AnalyticsSnapshot).join(sub, (AnalyticsSnapshot.publication_id == sub.c.publication_id)
                                                         & (AnalyticsSnapshot.captured_at == sub.c.m))).all()
    return {r.publication_id: r for r in rows}


def performance(ctx: Ctx, *, channel_id=None, date_from=None, date_to=None) -> list[dict]:
    stmt = select(Publication).where(Publication.data_mode == ctx.mode, Publication.status == "PUBLISHED")
    if channel_id:
        stmt = stmt.where(Publication.channel_id == channel_id)
    if date_from:
        stmt = stmt.where(Publication.published_at >= date_from)
    if date_to:
        stmt = stmt.where(Publication.published_at <= date_to)
    pubs = ctx.db.scalars(stmt).all()
    snaps = _latest_snapshots(ctx, [p.id for p in pubs])
    out = []
    for pub in pubs:
        s = snaps.get(pub.id)
        proj = ctx.db.get(Project, pub.project_id)
        cost = float(spent(ctx.db, ctx.mode, project_id=pub.project_id))
        views = s.views if s else 0
        inter = (s.likes + s.comments + s.shares + s.saves) if s else 0
        out.append({
            "publication_id": str(pub.id), "project_id": str(pub.project_id), "project_code": proj.code, "title": proj.title,
            "channel_id": str(pub.channel_id), "platform": pub.platform, "post_url": pub.post_url,
            "published_at": pub.published_at.isoformat() if pub.published_at else None,
            "views": views, "likes": s.likes if s else 0, "comments": s.comments if s else 0,
            "shares": s.shares if s else 0, "saves": s.saves if s else 0,
            "retention_rate": s.retention_rate if s else None, "avg_watch_sec": s.avg_watch_sec if s else None,
            "conversions": s.conversions if s else None,
            "engagement_rate": round(inter / views * 100, 2) if views else None,
            "cost": cost, "cost_per_1k_views": round(cost / views * 1000, 0) if views else None,
            "cost_per_conversion": round(cost / s.conversions, 0) if s and s.conversions else None,
            "has_data": s is not None, "data_mode": pub.data_mode,
        })
    return sorted(out, key=lambda r: r["views"], reverse=True)


def insights(ctx: Ctx, channel_id=None) -> dict:
    """A10: so sánh & phát hiện bất thường bằng thống kê đơn giản."""
    rows = [r for r in performance(ctx, channel_id=channel_id) if r["has_data"]]

    def work(_llm, _actx):
        if len(rows) < 2:
            return {"result": {"insights": ["Cần ít nhất 2 video có số liệu để so sánh"], "anomalies": []}}, None
        med_views = statistics.median(r["views"] for r in rows)
        er = [r["engagement_rate"] for r in rows if r["engagement_rate"] is not None]
        med_er = statistics.median(er) if er else 0
        anomalies = [{"publication_id": r["publication_id"], "project_code": r["project_code"],
                      "reason": f"Lượt xem {r['views']} < 50% trung vị ({med_views:.0f})"} for r in rows if r["views"] < med_views * 0.5]
        best = max(rows, key=lambda r: r["engagement_rate"] or 0)
        notes = [f"Trung vị lượt xem: {med_views:,.0f}; trung vị tương tác: {med_er:.2f}%",
                 f"Tương tác cao nhất: {best['project_code']} ({best['engagement_rate']}%) trên {best['platform']}"]
        by_platform = defaultdict(list)
        for r in rows:
            by_platform[r["platform"]].append(r["views"])
        notes += [f"{k}: TB {sum(v) / len(v):,.0f} lượt xem/video ({len(v)} video)" for k, v in by_platform.items()]
        return {"result": {"insights": notes, "anomalies": anomalies, "median_views": med_views, "median_engagement": med_er}}, None

    run = run_agent(ctx, "A10", "analytics.insights", work, input_ref={"videos": len(rows)})
    return run.output["result"]


def export_csv(ctx: Ctx, **filters) -> str:
    rows = performance(ctx, **filters)
    buf = io.StringIO()
    cols = ["project_code", "title", "platform", "post_url", "published_at", "views", "likes", "comments", "shares", "saves",
            "retention_rate", "conversions", "engagement_rate", "cost", "cost_per_1k_views", "data_mode"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


# ======================= DASHBOARD CEO (M01) =======================
def dashboard(ctx: Ctx, *, channel_id=None, date_from=None, date_to=None, project_id=None, owner_id=None) -> dict:
    db, mode = ctx.db, ctx.mode
    date_to = date_to or _now()
    date_from = date_from or (date_to - timedelta(days=30))
    pq = select(Project).where(Project.data_mode == mode, Project.deleted_at.is_(None))
    if channel_id:
        pq = pq.where(Project.channel_id == channel_id)
    if project_id:
        pq = pq.where(Project.id == project_id)
    if owner_id:
        pq = pq.where(Project.owner_id == owner_id)
    all_projects = db.scalars(pq).all()
    in_range = [p for p in all_projects if date_from <= p.created_at <= date_to]
    ids = [p.id for p in all_projects]
    by_status = defaultdict(int)
    for p in all_projects:
        by_status[p.status] += 1
    cnt = lambda states: sum(by_status[s] for s in states)  # noqa: E731

    cost_q = select(func.coalesce(func.sum(CostRecord.amount), 0)).where(CostRecord.data_mode == mode,
                                                                          CostRecord.created_at >= date_from,
                                                                          CostRecord.created_at <= date_to)
    if channel_id or project_id or owner_id:
        cost_q = cost_q.where(CostRecord.project_id.in_(ids)) if ids else cost_q.where(False)
    total_cost = Decimal(db.scalar(cost_q) or 0)
    simulated_q = cost_q.where(CostRecord.is_simulated)
    simulated_cost = Decimal(db.scalar(simulated_q) or 0)
    approved = [p for p in all_projects if p.status in COMPLETED]
    approved_cost = sum((spent(db, mode, project_id=p.id) for p in approved), Decimal(0))

    human_reviews = db.scalars(select(QCReview).where(QCReview.data_mode == mode, QCReview.review_type == "FINAL",
                                                      QCReview.reviewer_type == "HUMAN",
                                                      QCReview.project_id.in_(ids) if ids else False)).all()
    avg_qc = round(sum(r.total_score for r in human_reviews) / len(human_reviews), 1) if human_reviews else None
    qc_pass_rate = round(sum(r.result == "PASS" for r in human_reviews) / len(human_reviews) * 100, 1) if human_reviews else None

    jobs = db.execute(select(GenerationJob.scene_id, func.count()).where(GenerationJob.data_mode == mode,
                                                                         GenerationJob.project_id.in_(ids) if ids else False)
                      .group_by(GenerationJob.scene_id)).all()
    scenes_generated = len(jobs)
    scenes_regenerated = sum(1 for _, n in jobs if n > 1)
    regen_rate = round(scenes_regenerated / scenes_generated * 100, 1) if scenes_generated else None

    fb_q = select(FeedbackCase).where(FeedbackCase.data_mode == mode)
    if channel_id:
        fb_q = fb_q.where(FeedbackCase.channel_id == channel_id)
    cases = db.scalars(fb_q).all()
    with_capa = [c for c in cases if c.status in ("ACTION_APPROVED", "IN_PROGRESS", "VERIFY_PENDING", "VERIFIED", "STANDARDIZED",
                                                  "CLOSED", "REOPENED")]
    verified = [c for c in with_capa if c.status in ("VERIFIED", "STANDARDIZED", "CLOSED")]
    capa_rate = round(len(verified) / len(with_capa) * 100, 1) if with_capa else None

    perf = performance(ctx, channel_id=channel_id)
    perf = [r for r in perf if (not ids or r["project_id"] in {str(i) for i in ids})]
    with_data = [r for r in perf if r["has_data"]]
    total_views = sum(r["views"] for r in with_data)
    ers = [r["engagement_rate"] for r in with_data if r["engagement_rate"] is not None]

    # Chuỗi thời gian theo ngày
    series = defaultdict(lambda: {"created": 0, "approved": 0, "published": 0, "cost": 0.0})
    for p in in_range:
        series[p.created_at.date().isoformat()]["created"] += 1
    for p in all_projects:
        if p.approved_at and date_from <= p.approved_at <= date_to:
            series[p.approved_at.date().isoformat()]["approved"] += 1
    for r in perf:
        if r["published_at"]:
            d = r["published_at"][:10]
            if date_from.date().isoformat() <= d <= date_to.date().isoformat():
                series[d]["published"] += 1
    cost_rows = db.execute(select(func.date(CostRecord.created_at), func.sum(CostRecord.amount)).where(
        CostRecord.data_mode == mode, CostRecord.created_at >= date_from, CostRecord.created_at <= date_to)
        .group_by(func.date(CostRecord.created_at))).all()
    for d, amt in cost_rows:
        series[d.isoformat()]["cost"] = float(amt)
    days = []
    d = date_from.date()
    while d <= date_to.date():
        days.append({"date": d.isoformat(), **series[d.isoformat()]})
        d += timedelta(days=1)

    # Cảnh báo ngân sách
    alerts = []
    for lim in db.scalars(select(BudgetLimit).where(BudgetLimit.data_mode == mode)).all():
        start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) if lim.period == "MONTHLY" else \
            _now().replace(hour=0, minute=0, second=0, microsecond=0)
        used = spent(db, mode, since=start, channel_id=lim.scope_ref if lim.scope == "CHANNEL" else None,
                     provider_code=lim.scope_ref if lim.scope == "PROVIDER" else None)
        pct = float(used / Decimal(lim.limit_amount) * 100) if lim.limit_amount else 0
        if pct >= lim.alert_threshold_pct:
            alerts.append({"scope": lim.scope, "ref": lim.scope_ref, "period": lim.period, "used": float(used),
                           "limit": float(lim.limit_amount), "pct": round(pct, 1),
                           "level": "CRITICAL" if pct >= 100 else "WARNING"})
    for p in all_projects:
        if p.budget_limit and p.budget_limit > 0 and p.status not in ("CANCELLED",):
            used = spent(db, mode, project_id=p.id)
            pct = float(used / Decimal(p.budget_limit) * 100)
            if pct >= 80:
                alerts.append({"scope": "PROJECT", "ref": p.code, "period": "TOTAL", "used": float(used),
                               "limit": float(p.budget_limit), "pct": round(pct, 1),
                               "level": "CRITICAL" if pct >= 100 else "WARNING"})

    def kpi(key, label, value, formula, source, unit="", note=""):
        return {"key": key, "label": label, "value": value, "unit": unit, "formula": formula, "source": source, "note": note}

    sim_note = "Bao gồm chi phí MÔ PHỎNG (DEMO)" if simulated_cost > 0 else ""
    kpis = [
        kpi("videos_total", "Tổng video (trong kỳ)", len(in_range), "COUNT(projects) có created_at trong kỳ", "projects"),
        kpi("in_production", "Đang sản xuất", cnt(IN_PRODUCTION), "COUNT(projects) trạng thái SCRIPT_GENERATING…FINAL_QC, RETRY_PENDING, NEEDS_MANUAL_ACTION", "projects.status"),
        kpi("pending_approval", "Chờ duyệt", cnt(PENDING_APPROVAL) + by_status["SCRIPT_REVIEW"], "COUNT(APPROVAL_PENDING) + COUNT(SCRIPT_REVIEW)", "projects.status"),
        kpi("completed", "Hoàn thành (đã duyệt)", cnt(COMPLETED), "COUNT(projects) trạng thái APPROVED trở đi", "projects.status"),
        kpi("published", "Đã phát hành", cnt(PUBLISHED), "COUNT(projects) trạng thái PUBLISHED, ANALYTICS_COLLECTION, FEEDBACK_REVIEW", "projects.status"),
        kpi("cost_total", "Chi phí sản xuất (kỳ)", float(total_cost), "SUM(cost_records.amount) trong kỳ", "cost_records", "VND", sim_note),
        kpi("cost_per_approved", "Chi phí / video đạt chuẩn", round(float(approved_cost) / len(approved)) if approved else None,
            "SUM(chi phí các dự án đã duyệt) / COUNT(dự án đã duyệt)", "cost_records + projects", "VND", sim_note),
        kpi("avg_qc", "Điểm QC trung bình", avg_qc, "AVG(qc_reviews.total_score) với review FINAL do người chấm", "qc_reviews", "/100"),
        kpi("qc_pass_rate", "Tỷ lệ đạt QC lần chấm", qc_pass_rate, "COUNT(PASS)/COUNT(review FINAL người chấm)", "qc_reviews", "%"),
        kpi("regen_rate", "Tỷ lệ cảnh phải tạo lại", regen_rate, "COUNT(cảnh có >1 generation_job) / COUNT(cảnh đã tạo)", "generation_jobs", "%"),
        kpi("feedback_cases", "Số Feedback Case", len(cases), "COUNT(feedback_cases)", "feedback_cases"),
        kpi("capa_verified_rate", "Tỷ lệ CAPA được xác minh", capa_rate,
            "COUNT(VERIFIED/STANDARDIZED/CLOSED) / COUNT(hồ sơ đã duyệt CAPA)", "feedback_cases", "%"),
        kpi("views_total", "Tổng lượt xem sau đăng", total_views, "SUM(views của snapshot mới nhất mỗi bài)", "analytics_snapshots"),
        kpi("engagement_avg", "Tương tác trung bình", round(sum(ers) / len(ers), 2) if ers else None,
            "AVG((likes+comments+shares+saves)/views)", "analytics_snapshots", "%"),
    ]
    return {
        "mode": mode, "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "filters": {"channel_id": str(channel_id) if channel_id else None, "project_id": str(project_id) if project_id else None,
                    "owner_id": str(owner_id) if owner_id else None},
        "kpis": kpis, "by_status": dict(by_status), "series": days, "top_videos": perf[:5], "budget_alerts": alerts,
        "simulated_cost": float(simulated_cost),
    }
