import uuid
from datetime import datetime

from app.api.schemas import ORM
from pydantic import BaseModel, Field

CONSENT = {"NOT_REQUIRED", "PENDING", "GRANTED", "REVOKED"}


class CharacterIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    age_range: str = ""
    gender: str = ""
    appearance: str = ""
    outfit: str = ""
    expressions: list[str] = Field(default_factory=list)
    personality: str = ""
    channel_id: uuid.UUID | None = None
    voice_profile_id: uuid.UUID | None = None
    consent_status: str = "NOT_REQUIRED"
    usage_rights: str = ""


class CharacterPatch(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    age_range: str | None = None
    gender: str | None = None
    appearance: str | None = None
    outfit: str | None = None
    expressions: list[str] | None = None
    personality: str | None = None
    channel_id: uuid.UUID | None = None
    voice_profile_id: uuid.UUID | None = None
    consent_status: str | None = None
    usage_rights: str | None = None


class ReferenceIn(BaseModel):
    ref_type: str
    asset_id: uuid.UUID
    note: str = ""


class ReferenceOut(ORM):
    id: uuid.UUID
    ref_type: str
    asset_id: uuid.UUID
    version_no: int
    note: str
    created_at: datetime


class LockOut(ORM):
    id: uuid.UUID
    version_no: int
    lock_data: dict
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    retired_at: datetime | None
    change_note: str
    created_at: datetime


class CharacterOut(ORM):
    id: uuid.UUID
    code: str
    channel_id: uuid.UUID | None
    name: str
    description: str
    age_range: str
    gender: str
    appearance: str
    outfit: str
    expressions: list
    personality: str
    voice_profile_id: uuid.UUID | None
    active_lock_id: uuid.UUID | None
    consent_status: str
    usage_rights: str
    status: str
    data_mode: str
    references: list[ReferenceOut] = []
    created_at: datetime


class VoiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    accent: str = "Miền Trung"
    gender: str = ""
    age_range: str = ""
    tone: str = ""
    speaking_rate: str = "vừa phải"
    provider_code: str = "manual"
    provider_voice_id: str | None = None
    audio_reference_asset_id: uuid.UUID | None = None
    consent_status: str = "PENDING"
    consent_document_asset_id: uuid.UUID | None = None
    usage_rights: str = ""
    rights_expires_at: datetime | None = None


class VoicePatch(BaseModel):
    name: str | None = None
    accent: str | None = None
    gender: str | None = None
    age_range: str | None = None
    tone: str | None = None
    speaking_rate: str | None = None
    provider_code: str | None = None
    provider_voice_id: str | None = None
    audio_reference_asset_id: uuid.UUID | None = None
    consent_status: str | None = None
    consent_document_asset_id: uuid.UUID | None = None
    usage_rights: str | None = None
    rights_expires_at: datetime | None = None


class VoiceOut(ORM):
    id: uuid.UUID
    code: str
    name: str
    accent: str
    gender: str
    age_range: str
    tone: str
    speaking_rate: str
    provider_code: str
    provider_voice_id: str | None
    audio_reference_asset_id: uuid.UUID | None
    consent_status: str
    consent_document_asset_id: uuid.UUID | None
    usage_rights: str
    rights_expires_at: datetime | None
    active_lock_id: uuid.UUID | None
    status: str
    data_mode: str
    created_at: datetime


class SceneLockIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    channel_id: uuid.UUID | None = None
    setting: str = Field(min_length=3)
    lighting: str = ""
    props: str = ""
    colors: str = ""
    reference_asset_ids: list[uuid.UUID] = Field(default_factory=list)
    base_code: str | None = None


class SceneLockOut(ORM):
    id: uuid.UUID
    code: str
    version_no: int
    channel_id: uuid.UUID | None
    name: str
    lock_data: dict
    status: str
    approved_at: datetime | None
    created_at: datetime
