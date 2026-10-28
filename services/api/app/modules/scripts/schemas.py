import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.api.schemas import ORM


class DialogueLine(BaseModel):
    speaker: str = Field(default="", max_length=120)
    text: str = Field(max_length=500)


class SceneIn(BaseModel):
    title: str = Field(default="", max_length=255)
    scene_type: str = Field(default="", max_length=60)
    action: str = Field(default="", max_length=2000)
    dialogue: list[DialogueLine] = Field(default_factory=list)
    setting: str = Field(default="", max_length=2000)
    camera: str = Field(default="", max_length=255)
    lighting: str = Field(default="", max_length=255)
    sound: str = Field(default="", max_length=255)
    duration_sec: int = Field(default=8, ge=1, le=30)
    character_ids: list[uuid.UUID] | None = None
    scene_lock_id: uuid.UUID | None = None


class ScriptIn(BaseModel):
    title: str = Field(default="", max_length=255)
    hook: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=20000)
    cta: str = Field(default="", max_length=255)
    scenes: list[SceneIn] = Field(max_length=20)
    note: str = Field(default="", max_length=255)


class SceneUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    scene_type: str | None = None
    action: str | None = None
    dialogue: list[DialogueLine] | None = None
    setting: str | None = None
    camera: str | None = None
    lighting: str | None = None
    sound: str | None = None
    duration_sec: int | None = Field(default=None, ge=1, le=30)
    character_ids: list[uuid.UUID] | None = None
    scene_lock_id: uuid.UUID | None = None
    note: str = ""


class SceneVersionOut(ORM):
    id: uuid.UUID
    version_no: int
    snapshot: dict
    change_note: str
    created_at: datetime


class SceneOut(ORM):
    id: uuid.UUID
    project_id: uuid.UUID
    order_index: int
    title: str
    scene_type: str
    duration_sec: int
    action: str
    dialogue: list
    setting: str
    camera: str
    lighting: str
    sound: str
    character_ids: list
    scene_lock_id: uuid.UUID | None
    prompt_text: str
    prompt_parts: dict
    negative_prompt: str
    prompt_version_id: uuid.UUID | None
    current_version_no: int
    status: str
    selected_asset_id: uuid.UUID | None
    versions: list[SceneVersionOut] = []


class ScriptVersionOut(ORM):
    id: uuid.UUID
    version_no: int
    title: str
    hook: str
    body: str
    cta: str
    scenes: list
    source: str
    change_note: str
    created_at: datetime
    agent_execution_id: uuid.UUID | None


class ScriptOut(ORM):
    id: uuid.UUID
    ideas: list
    selected_idea_index: int | None
    current_version_id: uuid.UUID | None
    approved_version_id: uuid.UUID | None
    status: str
    approved_at: datetime | None
