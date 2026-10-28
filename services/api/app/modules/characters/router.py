"""B03 API — Character & Voice Studio (M04)."""
import uuid

from app.api.deps import require
from app.core.context import Ctx
from app.core.errors import ValidationFailed
from app.modules.characters import service
from app.modules.characters.schemas import (
    CONSENT,
    CharacterIn,
    CharacterOut,
    CharacterPatch,
    LockOut,
    ReferenceIn,
    ReferenceOut,
    SceneLockIn,
    SceneLockOut,
    VoiceIn,
    VoiceOut,
    VoicePatch,
)
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(tags=["B03 Character & Voice Manager"])


class NoteIn(BaseModel):
    change_note: str = ""


def _consent(v):
    if v is not None and v not in CONSENT:
        raise ValidationFailed("Trạng thái consent không hợp lệ")


@router.get("/characters", response_model=list[CharacterOut])
def list_characters(channel_id: uuid.UUID | None = None, q: str | None = None, ctx: Ctx = Depends(require("character.view"))):
    return service.list_characters(ctx, channel_id, q)


@router.post("/characters", response_model=CharacterOut, status_code=201)
def create_character(data: CharacterIn, ctx: Ctx = Depends(require("character.edit"))):
    _consent(data.consent_status)
    c = service.create_character(ctx, data.model_dump())
    ctx.db.commit()
    return c


@router.get("/characters/{cid}")
def get_character(cid: uuid.UUID, ctx: Ctx = Depends(require("character.view"))):
    c = service.get_character(ctx, cid)
    return {"character": CharacterOut.model_validate(c).model_dump(mode="json"),
            "locks": [LockOut.model_validate(x).model_dump(mode="json") for x in service.character_locks(ctx, cid)],
            "readiness": service.lock_readiness(ctx, c)}


@router.patch("/characters/{cid}", response_model=CharacterOut)
def update_character(cid: uuid.UUID, data: CharacterPatch, ctx: Ctx = Depends(require("character.edit"))):
    _consent(data.consent_status)
    c = service.update_character(ctx, cid, data.model_dump(exclude_unset=True))
    ctx.db.commit()
    return c


@router.post("/characters/{cid}/references", response_model=ReferenceOut, status_code=201)
def add_reference(cid: uuid.UUID, data: ReferenceIn, ctx: Ctx = Depends(require("character.edit"))):
    r = service.add_reference(ctx, cid, data.ref_type, data.asset_id, data.note)
    ctx.db.commit()
    return r


@router.post("/characters/{cid}/locks", response_model=LockOut, status_code=201)
def create_lock(cid: uuid.UUID, data: NoteIn, ctx: Ctx = Depends(require("character.edit"))):
    lock = service.create_character_lock(ctx, cid, data.change_note)
    ctx.db.commit()
    return lock


@router.post("/character-locks/{lock_id}/approve", response_model=LockOut)
def approve_lock(lock_id: uuid.UUID, ctx: Ctx = Depends(require("character.lock_approve"))):
    lock = service.approve_character_lock(ctx, lock_id)
    ctx.db.commit()
    return lock


@router.get("/voices", response_model=list[VoiceOut])
def list_voices(ctx: Ctx = Depends(require("character.view"))):
    return service.list_voices(ctx)


@router.post("/voices", response_model=VoiceOut, status_code=201)
def create_voice(data: VoiceIn, ctx: Ctx = Depends(require("character.edit"))):
    _consent(data.consent_status)
    v = service.create_voice(ctx, data.model_dump())
    ctx.db.commit()
    return v


@router.get("/voices/{vid}")
def get_voice(vid: uuid.UUID, ctx: Ctx = Depends(require("character.view"))):
    v = service.get_voice(ctx, vid)
    return {"voice": VoiceOut.model_validate(v).model_dump(mode="json"),
            "locks": [LockOut.model_validate(x).model_dump(mode="json") for x in service.voice_locks(ctx, vid)]}


@router.patch("/voices/{vid}", response_model=VoiceOut)
def update_voice(vid: uuid.UUID, data: VoicePatch, ctx: Ctx = Depends(require("character.edit"))):
    _consent(data.consent_status)
    v = service.update_voice(ctx, vid, data.model_dump(exclude_unset=True))
    ctx.db.commit()
    return v


@router.post("/voices/{vid}/locks", response_model=LockOut, status_code=201)
def create_voice_lock(vid: uuid.UUID, data: NoteIn, ctx: Ctx = Depends(require("character.edit"))):
    lock = service.create_voice_lock(ctx, vid, data.change_note)
    ctx.db.commit()
    return lock


@router.post("/voice-locks/{lock_id}/approve", response_model=LockOut)
def approve_voice_lock(lock_id: uuid.UUID, ctx: Ctx = Depends(require("character.lock_approve"))):
    lock = service.approve_voice_lock(ctx, lock_id)
    ctx.db.commit()
    return lock


@router.get("/scene-locks", response_model=list[SceneLockOut])
def list_scene_locks(channel_id: uuid.UUID | None = None, all_versions: bool = False,
                     ctx: Ctx = Depends(require("character.view"))):
    return service.list_scene_locks(ctx, channel_id, latest_only=not all_versions)


@router.post("/scene-locks", response_model=SceneLockOut, status_code=201)
def create_scene_lock(data: SceneLockIn, ctx: Ctx = Depends(require("character.edit"))):
    sl = service.create_scene_lock(ctx, name=data.name, channel_id=data.channel_id, code=data.base_code,
                                   lock_data={"setting": data.setting, "lighting": data.lighting, "props": data.props,
                                              "colors": data.colors,
                                              "reference_asset_ids": [str(a) for a in data.reference_asset_ids]})
    ctx.db.commit()
    return sl


@router.post("/scene-locks/{lock_id}/approve", response_model=SceneLockOut)
def approve_scene_lock(lock_id: uuid.UUID, ctx: Ctx = Depends(require("character.lock_approve"))):
    sl = service.approve_scene_lock(ctx, lock_id)
    ctx.db.commit()
    return sl
