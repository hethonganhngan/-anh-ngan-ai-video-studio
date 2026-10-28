"""B06 — Render Engine service: timeline (M06), tác vụ render, lịch sử render."""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core import audit
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.errors import InvalidTransition, NotFound, ValidationFailed
from app.media.models import Asset
from app.modules.projects.models import Project
from app.modules.projects.service import get_project, lock_project
from app.modules.rendering import ffmpeg as F
from app.modules.rendering.models import Render, RenderJob
from app.modules.scripts.models import Scene
from app.workflows import state_machine as sm
from app.workflows.dispatch import defer

LOGO_POSITIONS = {"top_right", "top_left", "bottom_right", "bottom_left"}


def _asset(ctx: Ctx, aid, kinds: set[str], label: str) -> Asset:
    a = ctx.db.get(Asset, uuid.UUID(str(aid)))
    if a is None or a.deleted_at or a.data_mode != ctx.mode:
        raise ValidationFailed(f"{label}: tài nguyên không tồn tại", code="MISSING_ASSET")
    if a.mime_type.split("/")[0] not in kinds:
        raise ValidationFailed(f"{label}: tài nguyên {a.name} không đúng loại", code="INVALID_ASSET_TYPE")
    return a


def default_timeline(ctx: Ctx, p: Project) -> dict:
    scenes = ctx.db.scalars(select(Scene).where(Scene.project_id == p.id).order_by(Scene.order_index)).all()
    logo = ctx.db.scalar(select(Asset).where(Asset.asset_type == "LOGO", Asset.data_mode == ctx.mode, Asset.deleted_at.is_(None),
                                             (Asset.channel_id == p.channel_id) | (Asset.channel_id.is_(None)))
                         .order_by(Asset.channel_id.is_(None), Asset.created_at.desc()))
    return {
        "clips": [{"scene_id": str(s.id), "asset_id": str(s.selected_asset_id) if s.selected_asset_id else None,
                   "trim_start": 0.0, "trim_end": None, "volume": 1.0} for s in scenes],
        "subtitles": {"enabled": True, "burn_in": True, "font_size": 10},
        "voiceover": [],
        "music": None,
        "logo": {"asset_id": str(logo.id), "position": "top_right", "scale": 0.18, "opacity": 0.9} if logo else None,
        "thumbnail": {"time_sec": 1.0, "title": p.title[:60]},
    }


def get_timeline(ctx: Ctx, project_id) -> dict:
    p = get_project(ctx, project_id)
    return p.timeline if p.timeline else default_timeline(ctx, p)


def validate_timeline(ctx: Ctx, p: Project, tl: dict) -> dict:
    clips = tl.get("clips") or []
    if not clips:
        raise ValidationFailed("Timeline chưa có cảnh", code="EMPTY_TIMELINE")
    scene_ids = {str(s.id) for s in ctx.db.scalars(select(Scene).where(Scene.project_id == p.id)).all()}
    for i, c in enumerate(clips, 1):
        if str(c.get("scene_id")) not in scene_ids:
            raise ValidationFailed(f"Clip {i}: cảnh không thuộc dự án")
        if not c.get("asset_id"):
            raise ValidationFailed(f"Clip {i}: cảnh chưa có video", code="MISSING_ASSET")
        a = _asset(ctx, c["asset_id"], {"video"}, f"Clip {i}")
        ts, te = float(c.get("trim_start") or 0), c.get("trim_end")
        if ts < 0 or (te is not None and (float(te) <= ts or float(te) > (a.duration_sec or 0) + 0.05)):
            raise ValidationFailed(f"Clip {i}: điểm cắt không hợp lệ (0 ≤ đầu < cuối ≤ {a.duration_sec}s)", code="INVALID_TRIM")
    for j, vo in enumerate(tl.get("voiceover") or [], 1):
        _asset(ctx, vo["asset_id"], {"audio"}, f"Voice-over {j}")
        if float(vo.get("start", 0)) < 0:
            raise ValidationFailed("Thời điểm voice-over không hợp lệ")
    if tl.get("music"):
        _asset(ctx, tl["music"]["asset_id"], {"audio"}, "Nhạc nền")
        if not 0 <= float(tl["music"].get("volume", 0.15)) <= 1:
            raise ValidationFailed("Âm lượng nhạc nền 0–1")
    if tl.get("logo"):
        _asset(ctx, tl["logo"]["asset_id"], {"image"}, "Logo")
        if tl["logo"].get("position", "top_right") not in LOGO_POSITIONS:
            raise ValidationFailed("Vị trí logo không hợp lệ")
    return tl


def save_timeline(ctx: Ctx, project_id, tl: dict) -> dict:
    ctx.require("editor.edit")
    p = lock_project(ctx, project_id)
    if p.status not in ("SCENE_QC", "FINAL_QC", "RENDERING", "GENERATING", "NEEDS_MANUAL_ACTION", "APPROVAL_PENDING"):
        raise InvalidTransition(f"Không chỉnh timeline ở trạng thái {p.status}")
    validate_timeline(ctx, p, tl)
    before = p.timeline
    p.timeline = tl
    audit.record(ctx, "editor.timeline_save", "project", p.id, before={"clips": len((before or {}).get("clips", []))},
                 after={"clips": len(tl["clips"])})
    return tl


def start_render(ctx: Ctx, project, timeline: dict | None, actor_check: bool = True) -> RenderJob:
    if actor_check:
        ctx.require("render.run")
    p = project if isinstance(project, Project) else lock_project(ctx, project)
    if p.status not in ("SCENE_QC", "FINAL_QC", "RETRY_PENDING", "APPROVAL_PENDING"):
        raise InvalidTransition(f"Không thể render ở trạng thái {p.status}")
    scenes = ctx.db.scalars(select(Scene).where(Scene.project_id == p.id)).all()
    failed = [s.order_index + 1 for s in scenes if s.status == "QC_FAILED"]
    if failed:
        raise ValidationFailed(f"Cảnh {failed} chưa đạt QC — tạo lại hoặc miễn lỗi trước khi render", code="SCENE_QC_FAILED")
    tl = timeline or (p.timeline if p.timeline else default_timeline(ctx, p))
    validate_timeline(ctx, p, tl)
    p.timeline = tl
    active = ctx.db.scalar(select(RenderJob).where(RenderJob.project_id == p.id, RenderJob.status.in_(["QUEUED", "RUNNING"])))
    if active:
        return active
    n = (ctx.db.scalar(select(func.count()).select_from(RenderJob).where(RenderJob.project_id == p.id)) or 0) + 1
    digest = hashlib.sha1(json.dumps(tl, sort_keys=True).encode()).hexdigest()[:12]
    job = RenderJob(project_id=p.id, timeline=tl, idempotency_key=f"{p.id}:{digest}:{n}", requested_by=ctx.actor.user_uuid,
                    data_mode=ctx.mode, log=[{"msg": "Xếp hàng render"}])
    ctx.db.add(job)
    ctx.db.flush()
    if p.status == "APPROVAL_PENDING":
        sm.transition(ctx, p, "FINAL_QC", note="Render lại — cần QC lại")
    if p.status == "RETRY_PENDING":
        sm.transition(ctx, p, "RENDERING", note="Chạy lại render")
    else:
        sm.transition(ctx, p, "RENDERING", note=f"A06 render lần {n}")
    defer(ctx.db, "anngan.render.run_job", str(job.id))
    audit.record(ctx, "render.start", "project", p.id, after={"render_job": str(job.id)})
    return job


def _local(asset: Asset, cleanup: list) -> str:
    from app.media.storage import get_storage
    from app.workflows.jobs import tmp_path

    st = get_storage()
    lp = st.local_path(asset.storage_key)
    if lp:
        return lp
    path = tmp_path(os.path.splitext(asset.storage_key)[1])
    st.get_to_path(asset.storage_key, path)
    cleanup.append(path)
    return path


def execute_render(db, job: RenderJob) -> Render:
    """Chạy trong worker: dựng MP4 + SRT + thumbnail, lưu Object Storage, tạo bản Render mới."""
    from app.agents.runner import run_agent
    from app.media.probe import ffprobe, summarize
    from app.media.service import ingest_file
    from app.media.storage import safe_remove
    from app.workflows.jobs import _agent_ctx, _log, tmp_path

    s = get_settings()
    ctx = _agent_ctx(db, job.data_mode, "A06")
    p = db.get(Project, job.project_id)
    if p.status != "RENDERING":
        job.status = "CANCELLED"
        _log(job, f"Bỏ qua: dự án đang {p.status}")
        return None
    tl = job.timeline
    cleanup: list[str] = []
    out = tmp_path(".mp4")
    srt = tmp_path(".srt")
    thumb = tmp_path(".jpg")
    cleanup += [out, srt, thumb]
    try:
        def work(_llm, _actx):
            clips = []
            for c in tl["clips"]:
                a = db.get(Asset, uuid.UUID(c["asset_id"]))
                scene = db.get(Scene, uuid.UUID(c["scene_id"]))
                clips.append(F.ClipIn(path=_local(a, cleanup), duration=a.duration_sec or scene.duration_sec,
                                      has_audio=bool(a.media_info.get("has_audio")), trim_start=float(c.get("trim_start") or 0),
                                      trim_end=float(c["trim_end"]) if c.get("trim_end") is not None else None,
                                      dialogue=scene.dialogue, volume=float(c.get("volume", 1.0))))
            subs = tl.get("subtitles") or {}
            with open(srt, "w", encoding="utf-8") as f:
                f.write(F.build_srt(clips))
            plan = F.RenderPlan(clips=clips, output=out, srt_path=srt if subs.get("enabled", True) else None,
                                burn_subtitles=subs.get("burn_in", True), subtitle_font_size=int(subs.get("font_size", 10)),
                                width=s.output_width, height=s.output_height, fps=s.output_fps)
            if tl.get("logo"):
                lg = tl["logo"]
                plan.logo_path = _local(db.get(Asset, uuid.UUID(lg["asset_id"])), cleanup)
                plan.logo_position = lg.get("position", "top_right")
                plan.logo_scale = float(lg.get("scale", 0.18))
                plan.logo_opacity = float(lg.get("opacity", 0.9))
            for vo in tl.get("voiceover") or []:
                plan.voiceovers.append(F.AudioIn(_local(db.get(Asset, uuid.UUID(vo["asset_id"])), cleanup),
                                                 float(vo.get("start", 0)), float(vo.get("volume", 1.0))))
            if tl.get("music"):
                m = tl["music"]
                plan.music = F.AudioIn(_local(db.get(Asset, uuid.UUID(m["asset_id"])), cleanup), 0, float(m.get("volume", 0.15)))
                plan.music_fade_out = float(m.get("fade_out", 2.0))
            F.render(plan)
            th = tl.get("thumbnail") or {}
            F.make_thumbnail(clips[0].path, thumb, min(float(th.get("time_sec", 1.0)), clips[0].length - 0.1), th.get("title"))
            info = summarize(ffprobe(out))
            expected = sum(c.length for c in clips)
            problems = []
            if (info["width"], info["height"]) != (s.output_width, s.output_height):
                problems.append(f"Kích thước {info['width']}x{info['height']} ≠ {s.output_width}x{s.output_height}")
            if abs((info["duration_sec"] or 0) - expected) > 0.6:
                problems.append(f"Thời lượng {info['duration_sec']}s ≠ dự kiến {expected:.1f}s")
            if not info["has_audio"]:
                problems.append("Không có âm thanh")
            if problems:
                raise F.RenderError("; ".join(problems))
            return {"result": info, "summary": f"{expected:.1f}s"}, None

        run = run_agent(ctx, "A06", "render.execute", work, project=p, input_ref={"render_job": str(job.id), "clips": len(tl["clips"])})
        info = run.output["result"]
        n = (db.scalar(select(func.max(Render.version_no)).where(Render.project_id == p.id)) or 0) + 1
        base = f"{p.code}_render_v{n}"
        video = ingest_file(ctx, out, f"{base}.mp4", asset_type="VIDEO", source="RENDER", usage_rights="AI_GENERATED",
                            tags=["render", p.code], channel_id=p.channel_id, project_id=p.id,
                            rights_note="DEMO" if p.data_mode == "DEMO" else "")
        thumb_a = ingest_file(ctx, thumb, f"{base}_thumb.jpg", asset_type="THUMBNAIL", source="RENDER",
                              usage_rights="AI_GENERATED", tags=["thumbnail", p.code], channel_id=p.channel_id, project_id=p.id)
        srt_a = None
        if os.path.getsize(srt) > 0:
            srt_a = ingest_file(ctx, srt, f"{base}.srt", asset_type="SUBTITLE", source="RENDER", usage_rights="OWNED",
                                tags=["subtitle", p.code], channel_id=p.channel_id, project_id=p.id)
        render = Render(project_id=p.id, render_job_id=job.id, version_no=n, video_asset_id=video.id,
                        thumbnail_asset_id=thumb_a.id, subtitle_asset_id=srt_a.id if srt_a else None,
                        duration_sec=info["duration_sec"], width=info["width"], height=info["height"],
                        size_bytes=video.size_bytes, probe=info, data_mode=p.data_mode)
        db.add(render)
        job.status = "SUCCEEDED"
        job.finished_at = datetime.now(timezone.utc)
        _log(job, f"Hoàn tất render v{n}")
        db.flush()
        sm.transition(ctx, p, "FINAL_QC", note=f"Render v{n} xong — QC tổng thể")
        from app.modules.quality.service import run_final_auto_qc

        run_final_auto_qc(ctx, p, render)
        return render
    finally:
        for f in cleanup:
            safe_remove(f)


def renders(ctx: Ctx, project_id) -> list[Render]:
    get_project(ctx, project_id)
    return ctx.db.scalars(select(Render).where(Render.project_id == project_id).order_by(Render.version_no.desc())).all()


def render_jobs(ctx: Ctx, project_id=None) -> list[RenderJob]:
    stmt = select(RenderJob).where(RenderJob.data_mode == ctx.mode)
    if project_id:
        stmt = stmt.where(RenderJob.project_id == project_id)
    return ctx.db.scalars(stmt.order_by(RenderJob.created_at.desc()).limit(200)).all()


def latest_render(ctx: Ctx, project_id) -> Render | None:
    return ctx.db.scalar(select(Render).where(Render.project_id == project_id).order_by(Render.version_no.desc()))


def get_render(ctx: Ctx, render_id) -> Render:
    r = ctx.db.get(Render, render_id)
    if r is None or r.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy bản render")
    return r
