"""Nhập tài nguyên an toàn: whitelist đuôi file + magic bytes + giới hạn dung lượng + ffprobe + SHA-256."""
import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import or_, select, func, String, cast

from app.core import audit
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.errors import NotFound, ValidationFailed
from app.media.models import Asset
from app.media.probe import ffprobe, summarize
from app.media.storage import get_storage

ALLOWED = {
    ".mp4": ("video/mp4", "VIDEO"), ".mov": ("video/quicktime", "VIDEO"), ".webm": ("video/webm", "VIDEO"),
    ".png": ("image/png", "IMAGE"), ".jpg": ("image/jpeg", "IMAGE"), ".jpeg": ("image/jpeg", "IMAGE"),
    ".webp": ("image/webp", "IMAGE"),
    ".mp3": ("audio/mpeg", "AUDIO"), ".wav": ("audio/wav", "AUDIO"), ".m4a": ("audio/mp4", "AUDIO"),
    ".aac": ("audio/aac", "AUDIO"),
    ".srt": ("application/x-subrip", "TEXT"), ".vtt": ("text/vtt", "TEXT"),
    ".pdf": ("application/pdf", "DOC"), ".zip": ("application/zip", "ARCHIVE"), ".json": ("application/json", "TEXT"),
}
ASSET_TYPES = {"IMAGE", "VIDEO", "AUDIO", "LOGO", "CHARACTER", "BACKGROUND", "PRODUCT", "TEMPLATE", "REFERENCE",
               "SUBTITLE", "DOCUMENT", "THUMBNAIL", "EXPORT"}
USAGE_RIGHTS = {"OWNED", "LICENSED", "CONSENTED", "AI_GENERATED", "UNKNOWN"}
# Loại tài nguyên → nhóm định dạng cho phép
TYPE_KINDS = {
    "VIDEO": {"VIDEO"}, "AUDIO": {"AUDIO"}, "IMAGE": {"IMAGE"}, "LOGO": {"IMAGE"}, "CHARACTER": {"IMAGE"},
    "BACKGROUND": {"IMAGE", "VIDEO"}, "PRODUCT": {"IMAGE", "VIDEO"}, "TEMPLATE": {"IMAGE", "VIDEO", "TEXT"},
    "REFERENCE": {"IMAGE", "VIDEO", "AUDIO", "DOC", "TEXT"}, "SUBTITLE": {"TEXT"}, "DOCUMENT": {"DOC", "TEXT"},
    "THUMBNAIL": {"IMAGE"}, "EXPORT": {"ARCHIVE"},
}


def sanitize_filename(name: str) -> str:
    base = os.path.basename(name or "file")
    base = re.sub(r"[^\w.\- ]+", "_", base, flags=re.UNICODE).strip(" .") or "file"
    return base[:180]


def _magic_ok(path: str, ext: str) -> bool:
    with open(path, "rb") as f:
        head = f.read(64)
    if not head:
        return False
    if ext in (".mp4", ".mov", ".m4a"):
        return head[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free")
    if ext == ".webm":
        return head[:4] == b"\x1a\x45\xdf\xa3"
    if ext == ".png":
        return head[:8] == b"\x89PNG\r\n\x1a\n"
    if ext in (".jpg", ".jpeg"):
        return head[:3] == b"\xff\xd8\xff"
    if ext == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if ext == ".wav":
        return head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    if ext == ".mp3":
        return head[:3] == b"ID3" or (head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)
    if ext == ".aac":
        return head[0] == 0xFF and (head[1] & 0xF6) == 0xF0
    if ext == ".pdf":
        return head[:5] == b"%PDF-"
    if ext == ".zip":
        return head[:4] == b"PK\x03\x04"
    if ext in (".srt", ".vtt", ".json"):
        with open(path, "rb") as f:
            data = f.read(2_000_000)
        if b"\x00" in data:
            return False
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    return False


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_file(path: str, filename: str, asset_type: str) -> tuple[str, str, dict]:
    """Trả về (ext, mime, media_summary). Ném ValidationFailed nếu không hợp lệ."""
    s = get_settings()
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise ValidationFailed(f"Định dạng {ext or '(không có)'} không được phép", code="INVALID_FILE_TYPE",
                               details={"allowed": sorted(ALLOWED)})
    mime, kind = ALLOWED[ext]
    if asset_type not in ASSET_TYPES:
        raise ValidationFailed("Loại tài nguyên không hợp lệ", code="INVALID_ASSET_TYPE")
    if kind not in TYPE_KINDS[asset_type]:
        raise ValidationFailed(f"File {ext} không phù hợp loại {asset_type}", code="INVALID_FILE_TYPE")
    size = os.path.getsize(path)
    if size == 0:
        raise ValidationFailed("File rỗng", code="INVALID_FILE")
    if size > s.max_upload_mb * 1024 * 1024:
        raise ValidationFailed(f"File vượt {s.max_upload_mb}MB", code="FILE_TOO_LARGE")
    if not _magic_ok(path, ext):
        raise ValidationFailed("Nội dung file không khớp định dạng khai báo", code="INVALID_FILE_CONTENT")
    info: dict = {}
    if kind in ("VIDEO", "AUDIO", "IMAGE"):
        info = summarize(ffprobe(path))
        if kind == "VIDEO" and (not info.get("width") or not info.get("duration_sec")):
            raise ValidationFailed("File video không có luồng hình hợp lệ", code="INVALID_MEDIA")
        if kind == "AUDIO" and not info.get("has_audio"):
            raise ValidationFailed("File âm thanh không có luồng audio", code="INVALID_MEDIA")
    return ext, mime, info


def ingest_file(ctx: Ctx, path: str, filename: str, *, asset_type: str, name: str | None = None, source: str = "UPLOAD",
                usage_rights: str = "UNKNOWN", tags: list[str] | None = None, channel_id=None, project_id=None,
                scene_id=None, description: str = "", parent: Asset | None = None, extra_info: dict | None = None,
                rights_note: str = "") -> Asset:
    if usage_rights not in USAGE_RIGHTS:
        raise ValidationFailed("Quyền sử dụng không hợp lệ")
    ext, mime, info = validate_file(path, filename, asset_type)
    now = datetime.now(timezone.utc)
    key = f"{ctx.mode.lower()}/{now:%Y/%m}/{uuid.uuid4().hex}{ext}"
    storage = get_storage()
    storage.put_file(key, path, mime)
    asset = Asset(
        asset_type=asset_type, name=name or sanitize_filename(filename), description=description,
        storage_backend=storage.name, storage_key=key, mime_type=mime, size_bytes=os.path.getsize(path),
        checksum_sha256=sha256_file(path), duration_sec=info.get("duration_sec"), width=info.get("width"),
        height=info.get("height"), media_info={**info, **(extra_info or {}), "original_filename": sanitize_filename(filename)},
        tags=tags or [], usage_rights=usage_rights, rights_note=rights_note, source=source, channel_id=channel_id,
        project_id=project_id, scene_id=scene_id, uploaded_by=ctx.actor.user_uuid, data_mode=ctx.mode,
        version_no=(parent.version_no + 1) if parent else 1, parent_asset_id=parent.id if parent else None,
    )
    ctx.db.add(asset)
    ctx.db.flush()
    audit.record(ctx, "asset.create", "asset", asset.id,
                 after={"name": asset.name, "type": asset_type, "source": source, "size": asset.size_bytes})
    return asset


def get_asset(ctx: Ctx, asset_id) -> Asset:
    a = ctx.db.get(Asset, asset_id)
    if a is None or a.deleted_at is not None or a.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy tài nguyên")
    return a


def list_assets(ctx: Ctx, *, asset_type=None, q=None, tag=None, channel_id=None, project_id=None, usage_rights=None,
                include_versions=False, page=1, page_size=50):
    stmt = select(Asset).where(Asset.data_mode == ctx.mode, Asset.deleted_at.is_(None))
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Asset.name.ilike(like), Asset.description.ilike(like), cast(Asset.tags, String).ilike(like)))
    if tag:
        stmt = stmt.where(Asset.tags.contains([tag]))
    if channel_id:
        stmt = stmt.where(Asset.channel_id == channel_id)
    if project_id:
        stmt = stmt.where(Asset.project_id == project_id)
    if usage_rights:
        stmt = stmt.where(Asset.usage_rights == usage_rights)
    if not include_versions:
        # chỉ hiện phiên bản mới nhất của mỗi chuỗi version
        child = Asset.__table__.alias("child")
        stmt = stmt.where(~select(child.c.id).where(child.c.parent_asset_id == Asset.id, child.c.deleted_at.is_(None)).exists())
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = ctx.db.scalars(stmt.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return items, total
