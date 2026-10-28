"""B04 — Prompt Engine: template có phiên bản; lắp prompt 9 phần cho cảnh (A03, xác định)."""
import uuid
from datetime import datetime, timezone

from jinja2 import TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import func, select

from app.core import audit
from app.core.context import Ctx
from app.core.errors import NotFound, ValidationFailed
from app.modules.prompts.models import PromptTemplate, PromptVersion

_env = SandboxedEnvironment(autoescape=False)
PROMPT_PARTS = ["scene_type", "characters", "action", "setting", "camera", "lighting", "sound", "dialogue", "negative"]
PART_LABELS = {"scene_type": "Loại cảnh", "characters": "Nhân vật", "action": "Hành động", "setting": "Bối cảnh",
               "camera": "Máy quay", "lighting": "Ánh sáng", "sound": "Âm thanh", "dialogue": "Thoại",
               "negative": "Negative Prompt"}


def get_template(ctx: Ctx, code: str) -> PromptTemplate:
    t = ctx.db.scalar(select(PromptTemplate).where(PromptTemplate.code == code))
    if t is None:
        raise NotFound(f"Không có prompt template {code}")
    return t


def active_version(ctx: Ctx, template: PromptTemplate) -> PromptVersion:
    vid = template.demo_active_version_id if ctx.mode == "DEMO" else template.active_version_id
    vid = vid or template.active_version_id
    v = ctx.db.get(PromptVersion, vid) if vid else None
    if v is None:
        raise ValidationFailed(f"Template {template.code} chưa có phiên bản được kích hoạt", code="NO_ACTIVE_PROMPT")
    return v


def _set_active(ctx: Ctx, template: PromptTemplate, version_id) -> None:
    if ctx.mode == "DEMO":
        template.demo_active_version_id = version_id
    else:
        template.active_version_id = version_id


def create_version(ctx: Ctx, template_id, *, content: str, negative_prompt: str = "", rules: list | None = None,
                   change_note: str = "", source_lesson_id=None, actor_check: bool = True) -> PromptVersion:
    if actor_check:
        ctx.require("prompt.edit")
    tpl = ctx.db.get(PromptTemplate, template_id)
    if tpl is None:
        raise NotFound("Không tìm thấy template")
    try:
        _env.parse(content)
    except TemplateSyntaxError as e:
        raise ValidationFailed(f"Cú pháp template lỗi: {e.message}", code="TEMPLATE_SYNTAX")
    n = (ctx.db.scalar(select(func.max(PromptVersion.version_no)).where(PromptVersion.template_id == tpl.id)) or 0) + 1
    v = PromptVersion(template_id=tpl.id, version_no=n, content=content, negative_prompt=negative_prompt, rules=rules or [],
                      status="DRAFT", data_mode=ctx.mode, change_note=change_note[:255], source_lesson_id=source_lesson_id,
                      created_by=ctx.actor.user_uuid)
    ctx.db.add(v)
    ctx.db.flush()
    audit.record(ctx, "prompt.version_create", "prompt_version", v.id, after={"template": tpl.code, "version": n})
    return v


def approve_and_activate(ctx: Ctx, version_id, *, actor_check: bool = True) -> PromptVersion:
    """Chỉ người có prompt.approve (hoặc luồng Lesson đã được duyệt) mới kích hoạt prompt chuẩn."""
    if actor_check:
        ctx.require("prompt.approve")
    v = ctx.db.get(PromptVersion, version_id)
    if v is None:
        raise NotFound("Không tìm thấy phiên bản prompt")
    if v.data_mode != ctx.mode and v.data_mode != "PRODUCTION":
        raise ValidationFailed("Phiên bản DEMO không thể kích hoạt ở PRODUCTION", code="MODE_MISMATCH")
    tpl = ctx.db.get(PromptTemplate, v.template_id)
    before = {"active": str(tpl.demo_active_version_id if ctx.mode == "DEMO" else tpl.active_version_id)}
    if v.status == "DRAFT":
        v.status = "APPROVED"
        v.approved_by = ctx.actor.user_uuid
        v.approved_at = datetime.now(timezone.utc)
    elif v.status != "APPROVED":
        raise ValidationFailed("Chỉ kích hoạt phiên bản DRAFT/APPROVED")
    _set_active(ctx, tpl, v.id)
    audit.record(ctx, "prompt.activate", "prompt_template", tpl.id, before=before, after={"active": str(v.id), "mode": ctx.mode})
    return v


def set_active_version(ctx: Ctx, template: PromptTemplate, version_id) -> None:
    _set_active(ctx, template, version_id)


# ---------- A03: lắp prompt cảnh ----------
def _character_block(ctx: Ctx, character_ids: list) -> tuple[str, list[dict]]:
    from app.modules.characters.models import Character, CharacterLock

    descs, used = [], []
    for cid in character_ids or []:
        c = ctx.db.get(Character, uuid.UUID(str(cid)))
        if c is None:
            continue
        lock = ctx.db.get(CharacterLock, c.active_lock_id) if c.active_lock_id else None
        data = lock.lock_data if lock else {"name": c.name, "appearance": c.appearance, "outfit": c.outfit}
        descs.append(f"{c.code} {data.get('name', c.name)}: {data.get('appearance', '')}; trang phục: {data.get('outfit', '')}"
                     + (f" [Character Lock v{lock.version_no}]" if lock else " [CHƯA KHOÁ]"))
        used.append({"character_id": str(c.id), "code": c.code, "lock_version": lock.version_no if lock else None})
    return " | ".join(descs) or "Không có nhân vật cố định", used


def build_scene_prompt(ctx: Ctx, project, scene) -> dict:
    from app.modules.characters.models import SceneLock

    tpl = get_template(ctx, "A03.scene_prompt")
    ver = active_version(ctx, tpl)
    char_ids = scene.character_ids or project.character_ids or []
    characters, used = _character_block(ctx, char_ids)
    setting = scene.setting or project.setting
    scene_lock_info = None
    lock_id = scene.scene_lock_id or (uuid.UUID(project.scene_lock_ids[0]) if project.scene_lock_ids else None)
    if lock_id:
        sl = ctx.db.get(SceneLock, lock_id)
        if sl is not None:
            setting = f"{sl.lock_data.get('setting', sl.name)}; đạo cụ: {sl.lock_data.get('props', '')}; màu chủ đạo: {sl.lock_data.get('colors', '')} [Scene Lock {sl.code} v{sl.version_no}]"
            scene_lock_info = {"code": sl.code, "version": sl.version_no}
    dialogue = " / ".join(f"{d.get('speaker', '')}: \"{d.get('text', '')}\"" for d in (scene.dialogue or [])) or "Không thoại"
    negative = ver.negative_prompt
    parts = {
        "scene_type": scene.scene_type or "Cảnh kể chuyện", "characters": characters, "action": scene.action,
        "setting": setting, "camera": scene.camera or "Trung cảnh, máy quay ổn định", "lighting": scene.lighting or "Ánh sáng tự nhiên",
        "sound": scene.sound or "Thoại rõ, nhạc nền nhẹ", "dialogue": dialogue, "negative": negative,
    }
    text = _env.from_string(ver.content).render(**parts, aspect_ratio=project.aspect_ratio, duration=scene.duration_sec,
                                                rules=ver.rules or [])
    return {"prompt_text": text, "parts": parts, "negative_prompt": negative, "prompt_version_id": ver.id,
            "prompt_version_label": f"{tpl.code} v{ver.version_no}", "characters_used": used, "scene_lock": scene_lock_info}
