"""M12 — Thư viện tài nguyên API."""
import os
import tempfile
import uuid
from datetime import datetime, timezone

from app.api.deps import require
from app.api.schemas import Page
from app.core import audit
from app.core.config import get_settings
from app.core.context import Ctx
from app.core.errors import ValidationFailed
from app.media.schemas import AssetOut, AssetUpdate
from app.media.service import USAGE_RIGHTS, get_asset, ingest_file, list_assets, sanitize_filename
from app.media.storage import get_storage, safe_remove, tmp_dir
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

router = APIRouter(prefix="/assets", tags=["M12 Thư viện tài nguyên"])


async def save_upload(file: UploadFile) -> str:
    limit = get_settings().max_upload_mb * 1024 * 1024
    fd, path = tempfile.mkstemp(dir=tmp_dir(), suffix=os.path.splitext(sanitize_filename(file.filename or ""))[1])
    total = 0
    with os.fdopen(fd, "wb") as out:
        while chunk := await file.read(1 << 20):
            total += len(chunk)
            if total > limit:
                out.close()
                safe_remove(path)
                raise ValidationFailed(f"File vượt {get_settings().max_upload_mb}MB", code="FILE_TOO_LARGE")
            out.write(chunk)
    return path


@router.get("", response_model=Page[AssetOut])
def list_(asset_type: str | None = None, q: str | None = None, tag: str | None = None, channel_id: uuid.UUID | None = None,
          project_id: uuid.UUID | None = None, usage_rights: str | None = None, include_versions: bool = False,
          page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), ctx: Ctx = Depends(require("asset.view"))):
    items, total = list_assets(ctx, asset_type=asset_type, q=q, tag=tag, channel_id=channel_id, project_id=project_id,
                               usage_rights=usage_rights, include_versions=include_versions, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=AssetOut, status_code=201)
async def upload(file: UploadFile = File(...), asset_type: str = Form(...), name: str | None = Form(None),
                 description: str = Form(""), tags: str = Form(""), usage_rights: str = Form("UNKNOWN"),
                 rights_note: str = Form(""), channel_id: uuid.UUID | None = Form(None),
                 project_id: uuid.UUID | None = Form(None), ctx: Ctx = Depends(require("asset.upload"))):
    path = await save_upload(file)
    try:
        asset = ingest_file(ctx, path, file.filename or "upload", asset_type=asset_type, name=name, description=description,
                            tags=[t.strip() for t in tags.split(",") if t.strip()], usage_rights=usage_rights,
                            rights_note=rights_note, channel_id=channel_id, project_id=project_id)
        ctx.db.commit()
        return asset
    finally:
        safe_remove(path)


@router.get("/{asset_id}", response_model=AssetOut)
def get(asset_id: uuid.UUID, ctx: Ctx = Depends(require("asset.view"))):
    return get_asset(ctx, asset_id)


@router.get("/{asset_id}/versions", response_model=list[AssetOut])
def versions(asset_id: uuid.UUID, ctx: Ctx = Depends(require("asset.view"))):
    from app.media.models import Asset

    a = get_asset(ctx, asset_id)
    chain = [a]
    while chain[-1].parent_asset_id:
        p = ctx.db.get(Asset, chain[-1].parent_asset_id)
        if p is None:
            break
        chain.append(p)
    return chain


@router.post("/{asset_id}/versions", response_model=AssetOut, status_code=201)
async def new_version(asset_id: uuid.UUID, file: UploadFile = File(...), ctx: Ctx = Depends(require("asset.upload"))):
    parent = get_asset(ctx, asset_id)
    path = await save_upload(file)
    try:
        asset = ingest_file(ctx, path, file.filename or "upload", asset_type=parent.asset_type, name=parent.name,
                            description=parent.description, tags=parent.tags, usage_rights=parent.usage_rights,
                            rights_note=parent.rights_note, channel_id=parent.channel_id, project_id=parent.project_id,
                            scene_id=parent.scene_id, parent=parent)
        ctx.db.commit()
        return asset
    finally:
        safe_remove(path)


@router.patch("/{asset_id}", response_model=AssetOut)
def update(asset_id: uuid.UUID, data: AssetUpdate, ctx: Ctx = Depends(require("asset.upload"))):
    a = get_asset(ctx, asset_id)
    changes = data.model_dump(exclude_unset=True)
    if "usage_rights" in changes and changes["usage_rights"] not in USAGE_RIGHTS:
        raise ValidationFailed("Quyền sử dụng không hợp lệ")
    before = {k: getattr(a, k) for k in changes}
    for k, v in changes.items():
        setattr(a, k, v)
    audit.record(ctx, "asset.update", "asset", a.id, before=before, after=changes)
    ctx.db.commit()
    return a


@router.delete("/{asset_id}")
def delete(asset_id: uuid.UUID, ctx: Ctx = Depends(require("asset.delete"))):
    a = get_asset(ctx, asset_id)
    a.deleted_at = datetime.now(timezone.utc)
    audit.record(ctx, "asset.delete", "asset", a.id, before={"name": a.name})
    ctx.db.commit()
    return {"ok": True}


@router.get("/{asset_id}/content")
def content(asset_id: uuid.UUID, download: bool = False, ctx: Ctx = Depends(require("asset.view"))):
    a = get_asset(ctx, asset_id)
    st = get_storage()
    disposition = "attachment" if download else "inline"
    local = st.local_path(a.storage_key)
    if local:
        return FileResponse(local, media_type=a.mime_type, filename=a.media_info.get("original_filename") or a.name,
                            content_disposition_type=disposition)
    url = st.presigned_url(a.storage_key)
    if url:
        return RedirectResponse(url)
    return StreamingResponse(st.open(a.storage_key), media_type=a.mime_type)
