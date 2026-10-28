import uuid
from datetime import datetime
from decimal import Decimal

from app.api.schemas import ORM
from pydantic import BaseModel, Field, field_validator

AUTOMATION = {"MANUAL", "ASSISTED", "AUTO"}


class ProjectCreate(BaseModel):
    channel_id: uuid.UUID
    title: str | None = Field(default=None, max_length=255)
    topic: str = Field(min_length=5, max_length=2000)
    objective: str = Field(default="", max_length=2000)
    target_audience: str = Field(default="", max_length=2000)
    duration_sec: int = Field(default=32, ge=8, le=120)
    quantity: int = Field(default=1, ge=1, le=20)
    style: str = Field(default="", max_length=160)
    character_ids: list[uuid.UUID] = Field(default_factory=list, max_length=6)
    scene_lock_ids: list[uuid.UUID] = Field(default_factory=list, max_length=6)
    setting: str = Field(default="", max_length=255)
    voice_profile_id: uuid.UUID | None = None
    cta: str = Field(default="", max_length=255)
    budget_limit: Decimal = Field(default=Decimal(0), ge=0, le=Decimal(1_000_000_000))
    automation_level: str = "ASSISTED"
    video_provider_code: str = "mock"
    owner_id: uuid.UUID | None = None
    deadline: datetime | None = None
    priority: str = "NORMAL"
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)

    @field_validator("automation_level")
    @classmethod
    def _auto(cls, v):
        if v not in AUTOMATION:
            raise ValueError("Mức tự động hoá phải là MANUAL, ASSISTED hoặc AUTO")
        return v

    @field_validator("priority")
    @classmethod
    def _prio(cls, v):
        if v not in {"LOW", "NORMAL", "HIGH", "URGENT"}:
            raise ValueError("Ưu tiên không hợp lệ")
        return v


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    objective: str | None = None
    target_audience: str | None = None
    style: str | None = None
    setting: str | None = None
    cta: str | None = None
    budget_limit: Decimal | None = Field(default=None, ge=0)
    owner_id: uuid.UUID | None = None
    deadline: datetime | None = None
    priority: str | None = None
    automation_level: str | None = None
    video_provider_code: str | None = None
    character_ids: list[uuid.UUID] | None = None
    voice_profile_id: uuid.UUID | None = None


class ChannelMini(ORM):
    id: uuid.UUID
    code: str
    name: str


class ProjectOut(ORM):
    id: uuid.UUID
    code: str
    channel_id: uuid.UUID
    channel: ChannelMini
    batch_id: uuid.UUID | None
    title: str
    topic: str
    objective: str
    target_audience: str
    duration_sec: int
    aspect_ratio: str
    style: str
    setting: str
    cta: str
    character_ids: list
    scene_lock_ids: list
    voice_profile_id: uuid.UUID | None
    budget_limit: Decimal
    automation_level: str
    video_provider_code: str
    status: str
    resume_status: str | None
    progress: int
    owner_id: uuid.UUID | None
    created_by: uuid.UUID | None
    deadline: datetime | None
    priority: str
    last_error: str | None
    retry_count: int
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    data_mode: str
    created_at: datetime
    updated_at: datetime


class WorkflowEventOut(ORM):
    id: uuid.UUID
    created_at: datetime
    from_status: str | None
    to_status: str
    actor_type: str
    actor_ref: str | None
    note: str
    payload: dict


class TransitionIn(BaseModel):
    note: str = Field(default="", max_length=2000)


class CreateResult(BaseModel):
    projects: list[ProjectOut]
    batch_id: uuid.UUID | None = None
    duplicate: bool = False
    estimate: dict
    warnings: list[str] = []
