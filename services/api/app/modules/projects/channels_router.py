"""M13 — Quản lý kênh & Brand DNA (thuộc B01). Brand DNA có version + lịch sử, không ghi đè mất dữ liệu."""
import uuid
from datetime import datetime, timezone

from app.api.deps import require
from app.core import audit
from app.core.context import Ctx
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.modules.projects.models import BrandProfile, Channel, Project
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

router = APIRouter(prefix="/channels", tags=["M13 Kênh & Brand DNA"])
BRAND_FIELDS = ["slogan", "brand_promise", "big_idea", "brand_voice", "audience", "content_pillars", "character_set",
                "voice_set", "scene_set", "cta_rules", "quality_rules", "publishing_rules", "forbidden_terms"]
PLATFORMS = {"FACEBOOK", "TIKTOK", "YOUTUBE", "ZALO"}


class BrandIn(BaseModel):
    slogan: str | None = None
    brand_promise: str | None = None
    big_idea: str | None = None
    brand_voice: list[str] | None = None
    audience: str | None = None
    content_pillars: list[str] | None = None
    character_set: list[str] | None = None
    voice_set: list[str] | None = None
    scene_set: list[str] | None = None
    cta_rules: list[str] | None = None
    quality_rules: list[str] | None = None
    publishing_rules: list[str] | None = None
    forbidden_terms: list[str] | None = None
    change_note: str = Field(default="", max_length=255)


class ChannelIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_]{2,40}$")
    name: str = Field(min_length=2, max_length=160)
    description: str = ""
    platforms: list[str] = Field(default_factory=list)


class ChannelPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    platforms: list[str] | None = None
    is_active: bool | None = None


def _brand(b: BrandProfile | None) -> dict | None:
    if b is None:
        return None
    return {**{k: getattr(b, k) for k in BRAND_FIELDS}, "version_no": b.version_no, "history": b.history,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None}


def _out(ctx: Ctx, c: Channel) -> dict:
    n = ctx.db.scalar(select(func.count()).select_from(Project).where(Project.channel_id == c.id, Project.data_mode == ctx.mode))
    return {"id": str(c.id), "code": c.code, "name": c.name, "description": c.description, "platforms": c.platforms,
            "is_active": c.is_active, "project_count": n,
            "publish_targets": c.publish_targets or {}, "brand": _brand(c.brand_profile)}


@router.get("")
def list_channels(ctx: Ctx = Depends(require("channel.view"))):
    return [_out(ctx, c) for c in ctx.db.scalars(select(Channel).where(Channel.deleted_at.is_(None)).order_by(Channel.created_at)).all()]


class FacebookTargetIn(BaseModel):
    page_id: str | None = Field(default=None, pattern=r"^\d{5,30}$")


@router.get("/facebook/pages")
def facebook_pages(ctx: Ctx = Depends(require("channel.edit"))):
    """Các Fanpage mà token Facebook (M15) quản lý được — để gắn vào kênh."""
    from app.modules.publishing.service import facebook_call_pages

    return facebook_call_pages(ctx)


def _live_channel(ctx: Ctx, cid: uuid.UUID) -> Channel:
    c = ctx.db.get(Channel, cid)
    if c is None or c.deleted_at:
        raise NotFound("Không tìm thấy kênh")
    return c


def _checked_page(ctx: Ctx, page_id: str) -> dict:
    """Kiểm tra token đọc được trang trước khi gắn. Hệ thống chỉ gửi BẢN NHÁP chờ duyệt."""
    from app.modules.publishing.service import facebook_page_check

    page = facebook_page_check(ctx, page_id)
    return {"page_id": page["id"], "page_name": page["name"], "mode": "DRAFT",
            "connected_at": datetime.now(timezone.utc).isoformat()}


def _set_fb_pages(c: Channel, pages: list[dict]) -> None:
    """Lưu danh sách Fanpage; FACEBOOK giữ trang đầu tiên (Fanpage mặc định) cho dữ liệu/đoạn mã cũ."""
    targets = dict(c.publish_targets or {})
    targets["FACEBOOK_PAGES"] = pages
    if pages:
        targets["FACEBOOK"] = pages[0]
        if "FACEBOOK" not in (c.platforms or []):
            c.platforms = [*(c.platforms or []), "FACEBOOK"]
    else:
        targets.pop("FACEBOOK", None)
    c.publish_targets = targets


@router.put("/{cid}/facebook")
def connect_facebook(cid: uuid.UUID, data: FacebookTargetIn, ctx: Ctx = Depends(require("channel.edit"))):
    """Thay toàn bộ Fanpage của kênh bằng một trang (page_id rỗng = bỏ gắn tất cả)."""
    c = _live_channel(ctx, cid)
    _set_fb_pages(c, [_checked_page(ctx, data.page_id)] if data.page_id else [])
    audit.record(ctx, "channel.facebook", "channel", c.id, after={"page": data.page_id})
    ctx.db.commit()
    return _out(ctx, c)


class FacebookPageIn(BaseModel):
    page_id: str = Field(pattern=r"^\d{5,30}$")


@router.post("/{cid}/facebook/pages", status_code=201)
def add_facebook_page(cid: uuid.UUID, data: FacebookPageIn, ctx: Ctx = Depends(require("channel.edit"))):
    """Thêm một Fanpage vào kênh. Video đã duyệt của kênh gửi bản nháp lên mọi Fanpage đã gắn."""
    from app.modules.publishing.service import fb_pages

    c = _live_channel(ctx, cid)
    pages = fb_pages(c)
    if any(str(x["page_id"]) == data.page_id for x in pages):
        raise Conflict("Fanpage này đã gắn với kênh")
    _set_fb_pages(c, [*pages, _checked_page(ctx, data.page_id)])
    audit.record(ctx, "channel.facebook_add", "channel", c.id, after={"page": data.page_id})
    ctx.db.commit()
    return _out(ctx, c)


@router.delete("/{cid}/facebook/pages/{page_id}")
def remove_facebook_page(cid: uuid.UUID, page_id: str, ctx: Ctx = Depends(require("channel.edit"))):
    """Gỡ một Fanpage khỏi kênh (không xoá trang hay bài trên Facebook)."""
    from app.modules.publishing.service import fb_pages

    c = _live_channel(ctx, cid)
    pages = fb_pages(c)
    if not any(str(x["page_id"]) == page_id for x in pages):
        raise NotFound("Fanpage không gắn với kênh này")
    _set_fb_pages(c, [x for x in pages if str(x["page_id"]) != page_id])
    audit.record(ctx, "channel.facebook_remove", "channel", c.id, before={"page": page_id})
    ctx.db.commit()
    return _out(ctx, c)


@router.get("/{cid}")
def get_channel(cid: uuid.UUID, ctx: Ctx = Depends(require("channel.view"))):
    c = ctx.db.get(Channel, cid)
    if c is None or c.deleted_at:
        raise NotFound("Không tìm thấy kênh")
    return _out(ctx, c)


@router.post("", status_code=201)
def create_channel(data: ChannelIn, ctx: Ctx = Depends(require("channel.edit"))):
    old = ctx.db.scalar(select(Channel).where(Channel.code == data.code))
    if old:
        raise Conflict("Mã kênh đã được dùng cho một kênh đã xoá — chọn mã khác" if old.deleted_at else "Mã kênh đã tồn tại")
    if set(data.platforms) - PLATFORMS:
        raise ValidationFailed("Nền tảng không hợp lệ")
    c = Channel(code=data.code, name=data.name, description=data.description, platforms=data.platforms)
    ctx.db.add(c)
    ctx.db.flush()
    ctx.db.add(BrandProfile(channel_id=c.id))
    audit.record(ctx, "channel.create", "channel", c.id, after={"code": c.code})
    ctx.db.commit()
    ctx.db.refresh(c)
    return _out(ctx, c)


@router.patch("/{cid}")
def update_channel(cid: uuid.UUID, data: ChannelPatch, ctx: Ctx = Depends(require("channel.edit"))):
    c = ctx.db.get(Channel, cid)
    if c is None:
        raise NotFound("Không tìm thấy kênh")
    ch = data.model_dump(exclude_unset=True)
    if "platforms" in ch and set(ch["platforms"]) - PLATFORMS:
        raise ValidationFailed("Nền tảng không hợp lệ")
    for k, v in ch.items():
        setattr(c, k, v)
    audit.record(ctx, "channel.update", "channel", c.id, after=ch)
    ctx.db.commit()
    return _out(ctx, c)


FINISHED = ("PUBLISHED", "ANALYTICS_COLLECTION", "FEEDBACK_REVIEW", "CANCELLED")


@router.delete("/{cid}")
def delete_channel(cid: uuid.UUID, ctx: Ctx = Depends(require("channel.edit"))):
    """Xoá mềm kênh: ẩn khỏi danh sách, không tạo dự án mới; dự án, bài đăng và Brand DNA cũ vẫn giữ nguyên.
    Chặn khi kênh còn dự án đang làm dở (mọi chế độ DEMO/PRODUCTION)."""
    c = _live_channel(ctx, cid)
    busy = ctx.db.scalars(select(Project.code).where(Project.channel_id == c.id, Project.deleted_at.is_(None),
                                                     Project.status.not_in(FINISHED)).order_by(Project.code)).all()
    if busy:
        raise Conflict(f"Kênh còn {len(busy)} dự án chưa hoàn tất ({', '.join(busy[:5])}{'…' if len(busy) > 5 else ''}). "
                       "Hoàn tất hoặc huỷ các dự án này, hoặc tắt 'Hoạt động' để tạm ngừng kênh.", code="CHANNEL_IN_USE")
    c.deleted_at = datetime.now(timezone.utc)
    c.is_active = False
    audit.record(ctx, "channel.delete", "channel", c.id, before={"code": c.code, "name": c.name})
    ctx.db.commit()
    return {"id": str(c.id), "deleted": True}


@router.put("/{cid}/brand")
def update_brand(cid: uuid.UUID, data: BrandIn, ctx: Ctx = Depends(require("channel.edit"))):
    c = ctx.db.get(Channel, cid)
    if c is None:
        raise NotFound("Không tìm thấy kênh")
    b = c.brand_profile or BrandProfile(channel_id=c.id)
    ctx.db.add(b)
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if k in BRAND_FIELDS}
    if not changes:
        raise ValidationFailed("Không có thay đổi")
    snapshot = {k: getattr(b, k) for k in BRAND_FIELDS}
    b.history = [*(b.history or []), {"version": b.version_no, "at": datetime.now(timezone.utc).isoformat(),
                                      "by": ctx.actor.label, "note": data.change_note, "data": snapshot}]
    for k, v in changes.items():
        setattr(b, k, v)
    b.version_no = (b.version_no or 1) + 1
    b.updated_by = ctx.actor.user_uuid
    audit.record(ctx, "brand.update", "brand_profile", b.id, before={k: snapshot[k] for k in changes}, after=changes)
    ctx.db.commit()
    ctx.db.refresh(c)
    return _out(ctx, c)
