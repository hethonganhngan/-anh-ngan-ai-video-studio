"""B03 — Character & Voice Manager. Lock đã duyệt là bất biến; muốn đổi phải tạo phiên bản mới và duyệt lại."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core import audit
from app.core.codes import next_code
from app.core.context import Ctx
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.media.models import Asset
from app.modules.characters.models import (
    Character, CharacterLock, CharacterReference, SceneLock, VoiceLock, VoiceProfile,
)

REQUIRED_REFS = ["FRONT", "THREE_QUARTER", "FULL_BODY"]
REF_TYPES = set(REQUIRED_REFS) | {"EXPRESSION", "OUTFIT"}
CHAR_FIELDS = ["name", "description", "age_range", "gender", "appearance", "outfit", "expressions", "personality",
               "channel_id", "voice_profile_id", "consent_status", "usage_rights"]
VOICE_FIELDS = ["name", "accent", "gender", "age_range", "tone", "speaking_rate", "provider_code", "provider_voice_id",
                "audio_reference_asset_id", "consent_status", "consent_document_asset_id", "usage_rights", "rights_expires_at"]
NOW = lambda: datetime.now(timezone.utc)  # noqa: E731


def _asset_ok(ctx: Ctx, asset_id, kinds: set[str]) -> Asset:
    a = ctx.db.get(Asset, asset_id)
    if a is None or a.deleted_at or a.data_mode != ctx.mode:
        raise ValidationFailed("Tài nguyên không tồn tại", code="MISSING_ASSET")
    if a.mime_type.split("/")[0] not in kinds and a.asset_type not in kinds:
        raise ValidationFailed(f"Tài nguyên {a.name} không đúng loại", code="INVALID_ASSET_TYPE")
    return a


# ---------- Character ----------
def get_character(ctx: Ctx, cid) -> Character:
    c = ctx.db.get(Character, cid)
    if c is None or c.deleted_at or c.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy nhân vật")
    return c


def list_characters(ctx: Ctx, channel_id=None, q=None):
    stmt = select(Character).where(Character.data_mode == ctx.mode, Character.deleted_at.is_(None))
    if channel_id:
        stmt = stmt.where(Character.channel_id == channel_id)
    if q:
        stmt = stmt.where(Character.name.ilike(f"%{q}%") | Character.code.ilike(f"%{q}%"))
    return ctx.db.scalars(stmt.order_by(Character.code)).all()


def create_character(ctx: Ctx, data: dict) -> Character:
    ctx.require("character.edit")
    c = Character(code=next_code(ctx.db, Character, "CHR"), data_mode=ctx.mode,
                  **{k: data[k] for k in CHAR_FIELDS if k in data})
    ctx.db.add(c)
    ctx.db.flush()
    audit.record(ctx, "character.create", "character", c.id, after={"code": c.code, "name": c.name})
    return c


def update_character(ctx: Ctx, cid, data: dict) -> Character:
    """Sửa hồ sơ nháp. Character Lock đang hiệu lực KHÔNG thay đổi theo."""
    ctx.require("character.edit")
    c = get_character(ctx, cid)
    before = {k: getattr(c, k) for k in data if k in CHAR_FIELDS}
    for k, v in data.items():
        if k in CHAR_FIELDS:
            setattr(c, k, v)
    audit.record(ctx, "character.update", "character", c.id, before=before, after={k: data[k] for k in before})
    return c


def add_reference(ctx: Ctx, cid, ref_type: str, asset_id, note: str = "") -> CharacterReference:
    ctx.require("character.edit")
    if ref_type not in REF_TYPES:
        raise ValidationFailed(f"Loại ảnh tham chiếu không hợp lệ: {ref_type}")
    c = get_character(ctx, cid)
    _asset_ok(ctx, asset_id, {"image", "IMAGE", "CHARACTER"})
    n = (ctx.db.scalar(select(func.max(CharacterReference.version_no)).where(
        CharacterReference.character_id == c.id, CharacterReference.ref_type == ref_type)) or 0) + 1
    ref = CharacterReference(character_id=c.id, ref_type=ref_type, asset_id=asset_id, version_no=n, note=note)
    ctx.db.add(ref)
    ctx.db.flush()
    ctx.db.refresh(c)
    audit.record(ctx, "character.reference_add", "character", c.id, after={"ref_type": ref_type, "version": n})
    return ref


def _latest_refs(c: Character) -> dict[str, CharacterReference]:
    latest: dict[str, CharacterReference] = {}
    for r in c.references:
        if r.ref_type not in latest or r.version_no > latest[r.ref_type].version_no:
            latest[r.ref_type] = r
    return latest


def lock_readiness(ctx: Ctx, c: Character) -> dict:
    refs = _latest_refs(c)
    missing = [r for r in REQUIRED_REFS if r not in refs]
    issues = [f"Thiếu ảnh {r}" for r in missing]
    if c.consent_status in ("PENDING", "REVOKED"):
        issues.append("Chưa có xác nhận đồng ý sử dụng hình ảnh (consent)")
    if not c.appearance.strip():
        issues.append("Thiếu mô tả ngoại hình")
    if not c.outfit.strip():
        issues.append("Thiếu mô tả trang phục")
    return {"ready": not issues, "issues": issues, "references": {k: str(v.asset_id) for k, v in refs.items()}}


def create_character_lock(ctx: Ctx, cid, change_note: str = "") -> CharacterLock:
    ctx.require("character.edit")
    c = get_character(ctx, cid)
    if ctx.db.scalar(select(CharacterLock.id).where(CharacterLock.character_id == c.id, CharacterLock.status == "DRAFT")):
        raise Conflict("Đã có một bản khoá nháp đang chờ duyệt")
    readiness = lock_readiness(ctx, c)
    refs = _latest_refs(c)
    data = {"code": c.code, "name": c.name, "description": c.description, "age_range": c.age_range, "gender": c.gender,
            "appearance": c.appearance, "outfit": c.outfit, "expressions": c.expressions, "personality": c.personality,
            "voice_profile_id": str(c.voice_profile_id) if c.voice_profile_id else None,
            "references": {k: {"asset_id": str(v.asset_id), "version": v.version_no,
                               "checksum": ctx.db.get(Asset, v.asset_id).checksum_sha256} for k, v in refs.items()},
            "readiness": readiness}
    n = (ctx.db.scalar(select(func.max(CharacterLock.version_no)).where(CharacterLock.character_id == c.id)) or 0) + 1
    lock = CharacterLock(character_id=c.id, version_no=n, lock_data=data, status="DRAFT", created_by=ctx.actor.user_uuid,
                         change_note=change_note[:255])
    ctx.db.add(lock)
    ctx.db.flush()
    audit.record(ctx, "character.lock_create", "character_lock", lock.id, after={"character": c.code, "version": n})
    return lock


def approve_character_lock(ctx: Ctx, lock_id) -> CharacterLock:
    ctx.require("character.lock_approve")
    lock = ctx.db.get(CharacterLock, lock_id)
    if lock is None:
        raise NotFound("Không tìm thấy bản khoá")
    c = get_character(ctx, lock.character_id)
    if lock.status != "DRAFT":
        raise Conflict("Bản khoá này đã được xử lý")
    if not lock.lock_data.get("readiness", {}).get("ready"):
        raise ValidationFailed("Bản khoá chưa đủ điều kiện", code="LOCK_NOT_READY", details=lock.lock_data.get("readiness"))
    if lock.created_by and str(lock.created_by) == ctx.actor.id and ctx.actor.role_code not in ("SUPER_ADMIN",):
        raise ValidationFailed("Người tạo bản khoá không được tự duyệt (nguyên tắc 4 mắt)", code="SELF_APPROVAL")
    if c.active_lock_id:
        old = ctx.db.get(CharacterLock, c.active_lock_id)
        if old and old.status == "APPROVED":
            old.status = "RETIRED"
            old.retired_at = NOW()
    lock.status = "APPROVED"
    lock.approved_by = ctx.actor.user_uuid
    lock.approved_at = NOW()
    c.active_lock_id = lock.id
    c.status = "LOCKED"
    audit.record(ctx, "character.lock_approve", "character_lock", lock.id, after={"character": c.code, "version": lock.version_no})
    return lock


def character_locks(ctx: Ctx, cid) -> list[CharacterLock]:
    c = get_character(ctx, cid)
    return ctx.db.scalars(select(CharacterLock).where(CharacterLock.character_id == c.id).order_by(CharacterLock.version_no.desc())).all()


# ---------- Voice ----------
def get_voice(ctx: Ctx, vid) -> VoiceProfile:
    v = ctx.db.get(VoiceProfile, vid)
    if v is None or v.deleted_at or v.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy giọng nói")
    return v


def list_voices(ctx: Ctx):
    return ctx.db.scalars(select(VoiceProfile).where(VoiceProfile.data_mode == ctx.mode, VoiceProfile.deleted_at.is_(None))
                          .order_by(VoiceProfile.code)).all()


def create_voice(ctx: Ctx, data: dict) -> VoiceProfile:
    ctx.require("character.edit")
    for k in ("audio_reference_asset_id", "consent_document_asset_id"):
        if data.get(k):
            _asset_ok(ctx, data[k], {"audio", "AUDIO", "application", "DOCUMENT", "REFERENCE"})
    v = VoiceProfile(code=next_code(ctx.db, VoiceProfile, "VOI"), data_mode=ctx.mode,
                     **{k: data[k] for k in VOICE_FIELDS if k in data})
    ctx.db.add(v)
    ctx.db.flush()
    audit.record(ctx, "voice.create", "voice_profile", v.id, after={"code": v.code, "name": v.name})
    return v


def update_voice(ctx: Ctx, vid, data: dict) -> VoiceProfile:
    ctx.require("character.edit")
    v = get_voice(ctx, vid)
    for k in ("audio_reference_asset_id", "consent_document_asset_id"):
        if data.get(k):
            _asset_ok(ctx, data[k], {"audio", "AUDIO", "application", "DOCUMENT", "REFERENCE"})
    before = {k: getattr(v, k) for k in data if k in VOICE_FIELDS}
    for k, val in data.items():
        if k in VOICE_FIELDS:
            setattr(v, k, val)
    audit.record(ctx, "voice.update", "voice_profile", v.id, before=before, after={k: data[k] for k in before})
    return v


def create_voice_lock(ctx: Ctx, vid, change_note: str = "") -> VoiceLock:
    ctx.require("character.edit")
    v = get_voice(ctx, vid)
    issues = []
    if v.consent_status != "GRANTED":
        issues.append("Chưa có consent sử dụng giọng nói")
    if not v.audio_reference_asset_id:
        issues.append("Thiếu audio tham chiếu")
    if v.rights_expires_at and v.rights_expires_at < NOW():
        issues.append("Quyền sử dụng giọng đã hết hạn")
    if issues:
        raise ValidationFailed("Chưa đủ điều kiện khoá giọng", code="LOCK_NOT_READY", details=issues)
    if ctx.db.scalar(select(VoiceLock.id).where(VoiceLock.voice_profile_id == v.id, VoiceLock.status == "DRAFT")):
        raise Conflict("Đã có bản khoá giọng nháp")
    audio = ctx.db.get(Asset, v.audio_reference_asset_id)
    n = (ctx.db.scalar(select(func.max(VoiceLock.version_no)).where(VoiceLock.voice_profile_id == v.id)) or 0) + 1
    lock = VoiceLock(voice_profile_id=v.id, version_no=n, status="DRAFT", created_by=ctx.actor.user_uuid, change_note=change_note,
                     lock_data={"code": v.code, "name": v.name, "accent": v.accent, "gender": v.gender, "tone": v.tone,
                                "speaking_rate": v.speaking_rate, "provider_code": v.provider_code,
                                "provider_voice_id": v.provider_voice_id,
                                "audio_reference": {"asset_id": str(audio.id), "checksum": audio.checksum_sha256},
                                "consent_status": v.consent_status, "usage_rights": v.usage_rights})
    ctx.db.add(lock)
    ctx.db.flush()
    audit.record(ctx, "voice.lock_create", "voice_lock", lock.id, after={"voice": v.code, "version": n})
    return lock


def approve_voice_lock(ctx: Ctx, lock_id) -> VoiceLock:
    ctx.require("character.lock_approve")
    lock = ctx.db.get(VoiceLock, lock_id)
    if lock is None or lock.status != "DRAFT":
        raise NotFound("Không có bản khoá giọng chờ duyệt")
    v = get_voice(ctx, lock.voice_profile_id)
    if v.active_lock_id:
        old = ctx.db.get(VoiceLock, v.active_lock_id)
        if old and old.status == "APPROVED":
            old.status = "RETIRED"
            old.retired_at = NOW()
    lock.status = "APPROVED"
    lock.approved_by = ctx.actor.user_uuid
    lock.approved_at = NOW()
    v.active_lock_id = lock.id
    v.status = "LOCKED"
    audit.record(ctx, "voice.lock_approve", "voice_lock", lock.id, after={"voice": v.code, "version": lock.version_no})
    return lock


def voice_locks(ctx: Ctx, vid) -> list[VoiceLock]:
    v = get_voice(ctx, vid)
    return ctx.db.scalars(select(VoiceLock).where(VoiceLock.voice_profile_id == v.id).order_by(VoiceLock.version_no.desc())).all()


# ---------- Scene Lock ----------
def list_scene_locks(ctx: Ctx, channel_id=None, latest_only=True):
    stmt = select(SceneLock).where(SceneLock.data_mode == ctx.mode)
    if channel_id:
        stmt = stmt.where(SceneLock.channel_id == channel_id)
    rows = ctx.db.scalars(stmt.order_by(SceneLock.code, SceneLock.version_no.desc())).all()
    if not latest_only:
        return rows
    seen, out = set(), []
    for r in rows:
        if r.code not in seen:
            seen.add(r.code)
            out.append(r)
    return out


def create_scene_lock(ctx: Ctx, *, name: str, lock_data: dict, channel_id=None, code: str | None = None) -> SceneLock:
    ctx.require("character.edit")
    for aid in lock_data.get("reference_asset_ids", []) or []:
        _asset_ok(ctx, uuid.UUID(str(aid)), {"image", "video", "IMAGE", "BACKGROUND", "REFERENCE"})
    if code:
        prev = ctx.db.scalar(select(SceneLock).where(SceneLock.code == code, SceneLock.data_mode == ctx.mode)
                             .order_by(SceneLock.version_no.desc()))
        if prev is None:
            raise NotFound("Scene Lock gốc không tồn tại")
        n = prev.version_no + 1
        channel_id = channel_id or prev.channel_id
    else:
        code, n = next_code(ctx.db, SceneLock, "SCN"), 1
    sl = SceneLock(code=code, version_no=n, name=name, lock_data=lock_data, channel_id=channel_id, status="DRAFT",
                   created_by=ctx.actor.user_uuid, data_mode=ctx.mode)
    ctx.db.add(sl)
    ctx.db.flush()
    audit.record(ctx, "scene_lock.create", "scene_lock", sl.id, after={"code": code, "version": n})
    return sl


def approve_scene_lock(ctx: Ctx, lock_id) -> SceneLock:
    ctx.require("character.lock_approve")
    sl = ctx.db.get(SceneLock, lock_id)
    if sl is None or sl.data_mode != ctx.mode or sl.status != "DRAFT":
        raise NotFound("Không có Scene Lock chờ duyệt")
    for old in ctx.db.scalars(select(SceneLock).where(SceneLock.code == sl.code, SceneLock.status == "APPROVED")):
        old.status = "RETIRED"
        old.retired_at = NOW()
    sl.status = "APPROVED"
    sl.approved_by = ctx.actor.user_uuid
    sl.approved_at = NOW()
    audit.record(ctx, "scene_lock.approve", "scene_lock", sl.id, after={"code": sl.code, "version": sl.version_no})
    return sl
