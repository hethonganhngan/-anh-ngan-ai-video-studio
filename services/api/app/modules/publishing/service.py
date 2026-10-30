"""B10 — Publishing Manager."""
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.core import audit
from app.core.context import Ctx
from app.core.errors import InvalidTransition, NotFound, ProviderUnavailable, ValidationFailed
from app.core.security import decrypt_secret
from app.media.models import Asset
from app.modules.administration.models import ProviderAccount
from app.modules.projects.models import BrandProfile, Channel, Project
from app.modules.projects.service import get_project, lock_project
from app.modules.publishing.models import Publication
from app.modules.quality.compliance import scan
from app.modules.rendering.models import Render
from app.providers.publishing.base import PUBLISHERS, URL_DOMAINS, PublisherNotConnected
from app.workflows import state_machine as sm
from sqlalchemy import select

PLATFORMS = set(PUBLISHERS)
AI_LABEL = "(*) Nhân vật minh hoạ, video có sử dụng AI."
AI_LABEL_RE = re.compile(r"minh h(oạ|ọa|oa)", re.I)
PUBLISHABLE = {"APPROVED", "PUBLISH_QUEUED", "PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW"}


def _now():
    return datetime.now(timezone.utc)


def get_pub(ctx: Ctx, pid) -> Publication:
    x = ctx.db.get(Publication, pid)
    if x is None or x.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy bài đăng")
    return x


def _approved_render(ctx: Ctx, p: Project) -> Render:
    r = ctx.db.scalar(select(Render).where(Render.project_id == p.id, Render.status == "APPROVED")
                      .order_by(Render.version_no.desc()))
    if r is None:
        raise ValidationFailed("Video chưa có bản render được phê duyệt", code="NOT_APPROVED")
    return r


def with_ai_label(caption: str) -> str:
    """Nhân vật trong video là nhân vật AI → mô tả bài luôn có ghi chú 'nhân vật minh hoạ' (D24), không thêm trùng."""
    if AI_LABEL_RE.search(caption):
        return caption
    return f"{caption.rstrip()}\n\n{AI_LABEL}" if caption.strip() else AI_LABEL


def check_caption(ctx: Ctx, channel_id, caption: str, hashtags: list[str]) -> list[dict]:
    bp = ctx.db.scalar(select(BrandProfile).where(BrandProfile.channel_id == channel_id))
    return [f.to_dict() for f in scan(caption + " " + " ".join(hashtags), bp.forbidden_terms if bp else [])]


def create_publication(ctx: Ctx, project_id, *, platform: str, caption: str, hashtags: list[str], scheduled_at=None,
                       publish_mode: str = "MANUAL") -> Publication:
    ctx.require("publish.manage")
    p = get_project(ctx, project_id)
    if p.status not in PUBLISHABLE:
        raise ValidationFailed("Chỉ lên lịch video đã được phê duyệt", code="NOT_APPROVED")
    if platform not in PLATFORMS:
        raise ValidationFailed("Nền tảng không hợp lệ")
    ch = ctx.db.get(Channel, p.channel_id)
    if ch.platforms and platform not in ch.platforms:
        raise ValidationFailed(f"Kênh {ch.name} không đăng trên {platform}")
    if publish_mode not in ("MANUAL", "API"):
        raise ValidationFailed("Chế độ đăng không hợp lệ")
    render = _approved_render(ctx, p)
    caption = with_ai_label(caption)
    tags = [h if h.startswith("#") else f"#{h}" for h in (t.strip() for t in hashtags) if h]
    issues = check_caption(ctx, p.channel_id, caption, tags)
    blocking = [i for i in issues if i["severity"] in ("CRITICAL", "MAJOR")]
    if blocking:
        raise ValidationFailed("Caption vi phạm quy tắc tuân thủ", code="CAPTION_COMPLIANCE", details=blocking)
    if scheduled_at and scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    pub = Publication(project_id=p.id, render_id=render.id, channel_id=p.channel_id, platform=platform, caption=caption,
                      hashtags=tags, scheduled_at=scheduled_at, publish_mode=publish_mode,
                      status="SCHEDULED" if scheduled_at else "DRAFT", created_by=ctx.actor.user_uuid, data_mode=ctx.mode)
    ctx.db.add(pub)
    ctx.db.flush()
    audit.record(ctx, "publish.create", "publication", pub.id, after={"platform": platform, "project": p.code})
    return pub


def update_publication(ctx: Ctx, pid, data: dict) -> Publication:
    ctx.require("publish.manage")
    pub = get_pub(ctx, pid)
    if pub.status in ("PUBLISHED", "CANCELLED"):
        raise InvalidTransition("Bài đã đăng/huỷ không sửa được")
    if "caption" in data:
        data = {**data, "caption": with_ai_label(data["caption"] or "")}
    if "caption" in data or "hashtags" in data:
        caption = data.get("caption", pub.caption)
        tags = data.get("hashtags", pub.hashtags)
        blocking = [i for i in check_caption(ctx, pub.channel_id, caption, tags) if i["severity"] in ("CRITICAL", "MAJOR")]
        if blocking:
            raise ValidationFailed("Caption vi phạm quy tắc tuân thủ", code="CAPTION_COMPLIANCE", details=blocking)
    for k in ("caption", "hashtags", "scheduled_at"):
        if k in data:
            setattr(pub, k, data[k])
    if pub.status in ("DRAFT", "SCHEDULED"):
        pub.status = "SCHEDULED" if pub.scheduled_at else "DRAFT"
    audit.record(ctx, "publish.update", "publication", pub.id, after={k: str(v) for k, v in data.items()})
    return pub


def _ensure_queued(ctx: Ctx, p: Project, note: str) -> None:
    if p.status == "APPROVED":
        sm.transition(ctx, p, "PUBLISH_QUEUED", note=note)


def export_package(ctx: Ctx, pid) -> Asset:
    """Chế độ xuất file: gói MP4 + thumbnail + SRT + caption để đăng thủ công."""
    from app.media.service import ingest_file
    from app.media.storage import get_storage, safe_remove
    from app.workflows.jobs import tmp_path

    ctx.require("publish.manage")
    pub = get_pub(ctx, pid)
    p = lock_project(ctx, pub.project_id)
    render = ctx.db.get(Render, pub.render_id)
    st = get_storage()
    zpath = tmp_path(".zip")
    tmp_files = []
    try:
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for aid, name in ((render.video_asset_id, "video.mp4"), (render.thumbnail_asset_id, "thumbnail.jpg"),
                              (render.subtitle_asset_id, "subtitles.srt")):
                if not aid:
                    continue
                a = ctx.db.get(Asset, aid)
                lp = st.local_path(a.storage_key)
                if not lp:
                    lp = tmp_path(os.path.splitext(a.storage_key)[1])
                    st.get_to_path(a.storage_key, lp)
                    tmp_files.append(lp)
                z.write(lp, name)
            z.writestr("caption.txt", pub.caption + "\n\n" + " ".join(pub.hashtags))
            z.writestr("metadata.json", json.dumps({
                "project": p.code, "title": p.title, "platform": pub.platform, "render_version": render.version_no,
                "scheduled_at": pub.scheduled_at.isoformat() if pub.scheduled_at else None, "data_mode": pub.data_mode,
                "note": "DỮ LIỆU DEMO — KHÔNG ĐĂNG CÔNG KHAI" if pub.data_mode == "DEMO" else "",
            }, ensure_ascii=False, indent=2))
        asset = ingest_file(ctx, zpath, f"{p.code}_{pub.platform}_package.zip", asset_type="EXPORT", source="RENDER",
                            usage_rights="OWNED", tags=["export", pub.platform.lower(), p.code], channel_id=p.channel_id,
                            project_id=p.id)
    finally:
        safe_remove(zpath)
        for f in tmp_files:
            safe_remove(f)
    pub.export_asset_id = asset.id
    if pub.status in ("DRAFT", "SCHEDULED"):
        pub.status = "EXPORTED"
    _ensure_queued(ctx, p, f"Xuất gói đăng {pub.platform}")
    audit.record(ctx, "publish.export", "publication", pub.id, after={"asset": str(asset.id)})
    return asset


def _validate_post_url(platform: str, url: str) -> str:
    u = urlparse(url.strip())
    if u.scheme != "https" or not u.netloc:
        raise ValidationFailed("URL bài đăng phải là https://", code="INVALID_POST_URL")
    host = u.netloc.lower().split(":")[0]
    if not any(host == d or host.endswith("." + d) for d in URL_DOMAINS[platform]):
        raise ValidationFailed(f"URL không thuộc {platform} ({', '.join(URL_DOMAINS[platform])})", code="INVALID_POST_URL")
    return url.strip()


def mark_published(ctx: Ctx, pid, post_url: str, published_at=None) -> Publication:
    """Cập nhật thủ công sau khi người phát hành đã đăng bài trên nền tảng."""
    ctx.require("publish.execute")
    pub = get_pub(ctx, pid)
    if pub.status in ("PUBLISHED", "CANCELLED"):
        raise InvalidTransition("Bài đã đăng hoặc đã huỷ")
    pub.post_url = _validate_post_url(pub.platform, post_url)
    pub.published_at = published_at or _now()
    pub.published_by = ctx.actor.user_uuid
    pub.status = "PUBLISHED"
    p = lock_project(ctx, pub.project_id)
    _ensure_queued(ctx, p, f"Đăng {pub.platform}")
    if p.status == "PUBLISH_QUEUED":
        sm.transition(ctx, p, "PUBLISHED", note=f"Đăng {pub.platform}: {pub.post_url}")
    audit.record(ctx, "publish.mark_published", "publication", pub.id, after={"url": pub.post_url})
    return pub


def publish_via_api(ctx: Ctx, pid) -> Publication:
    ctx.require("publish.execute")
    pub = get_pub(ctx, pid)
    if ctx.mode == "DEMO" or pub.data_mode == "DEMO":
        raise ValidationFailed("Dữ liệu DEMO không được tự động xuất bản. Dùng 'Xuất file' để xem gói đăng.",
                               code="DEMO_AUTO_PUBLISH_BLOCKED")
    if pub.status in ("PUBLISHED", "CANCELLED"):
        raise InvalidTransition("Bài đã đăng hoặc đã huỷ")
    cls = PUBLISHERS[pub.platform]
    acc = ctx.db.scalar(select(ProviderAccount).where(ProviderAccount.provider_code == cls.provider_code))
    if acc is None or not acc.is_enabled or acc.connection_status != "VERIFIED":
        raise ProviderUnavailable(f"{pub.platform}: chưa kết nối API chính thức đã xác minh", code="PUBLISHER_NOT_CONNECTED")
    publisher = cls(decrypt_secret(acc.secret_encrypted) if acc.secret_encrypted else None, acc.config)
    try:
        publisher.publish("", pub.caption)
    except PublisherNotConnected as e:
        pub.error_message = str(e)
        raise ProviderUnavailable(str(e), code="PUBLISHER_NOT_CONNECTED")
    return pub


def cancel_publication(ctx: Ctx, pid) -> Publication:
    ctx.require("publish.manage")
    pub = get_pub(ctx, pid)
    if pub.status == "PUBLISHED":
        raise InvalidTransition("Bài đã đăng — gỡ bài trên nền tảng rồi ghi nhận thủ công")
    pub.status = "CANCELLED"
    audit.record(ctx, "publish.cancel", "publication", pub.id)
    return pub


def calendar(ctx: Ctx, date_from=None, date_to=None, channel_id=None) -> list[Publication]:
    stmt = select(Publication).where(Publication.data_mode == ctx.mode)
    if date_from:
        stmt = stmt.where((Publication.scheduled_at >= date_from) | (Publication.published_at >= date_from))
    if date_to:
        stmt = stmt.where((Publication.scheduled_at <= date_to) | (Publication.published_at <= date_to))
    if channel_id:
        stmt = stmt.where(Publication.channel_id == channel_id)
    return ctx.db.scalars(stmt.order_by(Publication.scheduled_at.asc().nulls_last(), Publication.created_at.desc())).all()


def approved_videos(ctx: Ctx) -> list[Project]:
    return ctx.db.scalars(select(Project).where(Project.data_mode == ctx.mode, Project.deleted_at.is_(None),
                                                Project.status.in_(sorted(PUBLISHABLE)))
                          .order_by(Project.approved_at.desc().nulls_last())).all()
