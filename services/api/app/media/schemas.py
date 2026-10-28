import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.api.schemas import ORM


class AssetOut(ORM):
    id: uuid.UUID
    asset_type: str
    name: str
    description: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    duration_sec: float | None
    width: int | None
    height: int | None
    media_info: dict
    tags: list
    usage_rights: str
    rights_note: str
    rights_expires_at: datetime | None
    source: str
    version_no: int
    parent_asset_id: uuid.UUID | None
    channel_id: uuid.UUID | None
    project_id: uuid.UUID | None
    scene_id: uuid.UUID | None
    data_mode: str
    created_at: datetime


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    usage_rights: str | None = None
    rights_note: str | None = None
    rights_expires_at: datetime | None = None
