"""B02 — AI Script Engine: 3 ý tưởng → chấm → chọn → kịch bản/storyboard → chỉnh sửa có phiên bản → duyệt → prompt."""
import uuid
from datetime import datetime, timezone

from app.agents.roles import script_agent as A02
from app.agents.runner import run_agent
from app.core import audit
from app.core.context import Ctx
from app.core.errors import InvalidTransition, NotFound, ValidationFailed
from app.modules.administration.service import get_setting
from app.modules.characters.models import Character
from app.modules.projects.models import BrandProfile, Project
from app.modules.projects.service import get_project, lock_project
from app.modules.prompts import service as prompts
from app.modules.quality.compliance import scan
from app.modules.scripts.models import Scene, SceneVersion, Script, ScriptVersion
from app.modules.scripts.validation import validate_scenes
from app.workflows import state_machine as sm
from sqlalchemy import func, select

SCENE_FIELDS = ["title", "scene_type", "action", "dialogue", "setting", "camera", "lighting", "sound", "duration_sec",
                "character_ids", "scene_lock_id"]
EDITABLE_STATES = {"CREATED", "SCRIPT_GENERATING", "SCRIPT_REVIEW", "STORYBOARD_READY"}


def _brief(ctx: Ctx, p: Project) -> dict:
    bp = ctx.db.scalar(select(BrandProfile).where(BrandProfile.channel_id == p.channel_id))
    return {
        "topic": p.topic, "objective": p.objective, "target_audience": p.target_audience or (bp.audience if bp else ""),
        "duration_sec": p.duration_sec, "style": p.style, "setting": p.setting, "cta": p.cta,
        "channel_name": p.channel.name, "slogan": bp.slogan if bp else "", "brand_promise": bp.brand_promise if bp else "",
        "big_idea": bp.big_idea if bp else "", "brand_voice": ", ".join(bp.brand_voice) if bp else "",
        "content_pillars": bp.content_pillars if bp else [], "forbidden_terms": bp.forbidden_terms if bp else [],
        "cta_rules": bp.cta_rules if bp else [],
    }


def _characters(ctx: Ctx, p: Project) -> list[dict]:
    out = []
    for cid in p.character_ids or []:
        c = ctx.db.get(Character, uuid.UUID(str(cid)))
        if c:
            out.append({"id": str(c.id), "code": c.code, "name": c.name, "description": c.description})
    return out


def get_or_create_script(ctx: Ctx, p: Project) -> Script:
    s = ctx.db.scalar(select(Script).where(Script.project_id == p.id))
    if s is None:
        s = Script(project_id=p.id, data_mode=ctx.mode, ideas=[])
        ctx.db.add(s)
        ctx.db.flush()
    return s


def _system_prompt(ctx: Ctx, brief: dict) -> tuple[str, str]:
    tpl = prompts.get_template(ctx, "A02.script")
    ver = prompts.active_version(ctx, tpl)
    policy = get_setting(ctx.db, "generation.policy")
    text = A02.render_system_prompt(ver.content, {**brief, "scene_seconds": policy["scene_seconds"],
                                                   "forbidden_terms": ", ".join(brief["forbidden_terms"]),
                                                   "rules": ver.rules or []})
    return text, f"{tpl.code} v{ver.version_no}"


def generate_ideas(ctx: Ctx, project_id) -> Script:
    ctx.require("script.generate")
    p = lock_project(ctx, project_id)
    if p.status == "CREATED":
        sm.transition(ctx, p, "SCRIPT_GENERATING", note="A02 tạo 3 ý tưởng")
    elif p.status == "SCRIPT_REVIEW":
        sm.transition(ctx, p, "SCRIPT_GENERATING", note="Tạo lại ý tưởng")
    elif p.status == "RETRY_PENDING" and p.resume_status == "SCRIPT_GENERATING":
        sm.transition(ctx, p, "SCRIPT_GENERATING", note="Chạy lại bước kịch bản")
    elif p.status != "SCRIPT_GENERATING":
        raise InvalidTransition(f"Không thể tạo ý tưởng khi dự án ở trạng thái {p.status}")
    brief = _brief(ctx, p)
    system, label = _system_prompt(ctx, brief)
    user_prompt = A02.build_user_prompt_ideas(brief)

    def work(llm, actx):
        res = llm.complete_json(system=system, prompt=user_prompt, schema=A02.IDEA_SCHEMA, max_tokens=16000,
                                mock_fn=lambda: A02.mock_ideas(brief))
        return res.data, res

    run = run_agent(ctx, "A02", "script.ideas", work, project=p, needs_llm=True,
                    input_ref={"project": p.code, "prompt_version": label})
    ideas = run.output.get("ideas", [])[:3]
    if len(ideas) < 3:
        raise ValidationFailed("AI Script không trả đủ 3 ý tưởng", code="AGENT_BAD_OUTPUT")
    scored = []
    for i, idea in enumerate(ideas):
        sc = A02.score_idea(idea, brief)
        scored.append({**idea, "index": i, "score": sc["total"], "scores": sc["scores"],
                       "compliance_findings": sc["compliance_findings"], "scoring_method": sc["method"]})
    script = get_or_create_script(ctx, p)
    script.ideas = scored
    best = max(range(len(scored)), key=lambda i: scored[i]["score"])
    script.selected_idea_index = best if p.automation_level != "MANUAL" else None
    audit.record(ctx, "script.ideas", "script", script.id, after={"count": 3, "best": best,
                                                                   "execution": str(run.execution.id)})
    return script


def select_idea(ctx: Ctx, project_id, index: int) -> Script:
    ctx.require("script.edit")
    p = lock_project(ctx, project_id)
    script = get_or_create_script(ctx, p)
    if not script.ideas or not (0 <= index < len(script.ideas)):
        raise ValidationFailed("Ý tưởng không tồn tại")
    if p.status not in ("SCRIPT_GENERATING", "SCRIPT_REVIEW"):
        raise InvalidTransition("Chỉ chọn ý tưởng khi đang viết/duyệt kịch bản")
    if any(f["severity"] == "CRITICAL" for f in script.ideas[index].get("compliance_findings", [])):
        raise ValidationFailed("Ý tưởng vi phạm tuân thủ nghiêm trọng, không thể chọn", code="COMPLIANCE_CRITICAL")
    script.selected_idea_index = index
    audit.record(ctx, "script.select_idea", "script", script.id, after={"index": index})
    return script


def _next_version_no(ctx: Ctx, script: Script) -> int:
    return (ctx.db.scalar(select(func.max(ScriptVersion.version_no)).where(ScriptVersion.script_id == script.id)) or 0) + 1


def _sync_scenes(ctx: Ctx, p: Project, scenes_data: list[dict], note: str) -> list[Scene]:
    """Đồng bộ storyboard: cảnh đã có thì tạo SceneVersion mới, cảnh dư bị xoá (chỉ khi chưa sản xuất)."""
    policy = get_setting(ctx.db, "generation.policy")
    existing = {s.order_index: s for s in ctx.db.scalars(select(Scene).where(Scene.project_id == p.id)).all()}
    result = []
    for i, sd in enumerate(scenes_data):
        scene = existing.pop(i, None)
        values = {k: sd.get(k) for k in SCENE_FIELDS if k in sd}
        values.setdefault("duration_sec", policy["scene_seconds"])
        values["dialogue"] = [{"speaker": d.get("speaker", ""), "text": d.get("text", "")} for d in (values.get("dialogue") or [])]
        if "character_ids" in values:
            if values["character_ids"] is None:
                values.pop("character_ids")
            else:
                values["character_ids"] = [str(x) for x in values["character_ids"]]
        if values.get("scene_lock_id"):
            values["scene_lock_id"] = uuid.UUID(str(values["scene_lock_id"]))
        if scene is None:
            scene = Scene(project_id=p.id, order_index=i, data_mode=ctx.mode, character_ids=list(p.character_ids or []))
            ctx.db.add(scene)
            changed = True
        else:
            changed = any(getattr(scene, k) != v for k, v in values.items())
        for k, v in values.items():
            setattr(scene, k, v)
        ctx.db.flush()
        if changed:
            n = (ctx.db.scalar(select(func.max(SceneVersion.version_no)).where(SceneVersion.scene_id == scene.id)) or 0) + 1
            scene.current_version_no = n
            scene.status = "PLANNED"
            ctx.db.add(SceneVersion(scene_id=scene.id, version_no=n, snapshot=_scene_snapshot(scene), change_note=note[:255],
                                    created_by=ctx.actor.user_uuid))
        result.append(scene)
    for leftover in existing.values():
        ctx.db.delete(leftover)
    ctx.db.flush()
    return result


def _scene_snapshot(scene: Scene) -> dict:
    return {k: (str(getattr(scene, k)) if k == "scene_lock_id" and getattr(scene, k) else getattr(scene, k)) for k in SCENE_FIELDS}


def _check_script(ctx: Ctx, p: Project, data: dict) -> dict:
    policy = get_setting(ctx.db, "generation.policy")
    errors, warnings = validate_scenes(data.get("scenes", []), scene_seconds=policy["scene_seconds"],
                                       max_dialogue=policy["max_dialogue_lines"])
    brief = _brief(ctx, p)
    full_text = " ".join([data.get("hook", ""), data.get("body", ""), data.get("cta", "")] +
                         [d.get("text", "") for s in data.get("scenes", []) for d in s.get("dialogue", [])])
    findings = [f.to_dict() for f in scan(full_text, brief["forbidden_terms"])]
    if not (data.get("hook") or "").strip():
        errors.append("Thiếu hook 3 giây")
    return {"errors": errors, "warnings": warnings, "compliance": findings}


def write_script(ctx: Ctx, project_id) -> ScriptVersion:
    ctx.require("script.generate")
    p = lock_project(ctx, project_id)
    if p.status != "SCRIPT_GENERATING":
        raise InvalidTransition("Hãy tạo ý tưởng trước (trạng thái SCRIPT_GENERATING)")
    script = get_or_create_script(ctx, p)
    if script.selected_idea_index is None:
        raise ValidationFailed("Chưa chọn ý tưởng", code="IDEA_NOT_SELECTED")
    idea = script.ideas[script.selected_idea_index]
    brief = _brief(ctx, p)
    chars = _characters(ctx, p)
    policy = get_setting(ctx.db, "generation.policy")
    system, label = _system_prompt(ctx, brief)
    user_prompt = A02.build_user_prompt_script(brief, idea, chars, policy["scene_seconds"])

    def work(llm, actx):
        res = llm.complete_json(system=system, prompt=user_prompt, schema=A02.SCRIPT_SCHEMA, max_tokens=16000,
                                mock_fn=lambda: A02.mock_script(brief, idea, chars, policy["scene_seconds"]))
        return res.data, res

    run = run_agent(ctx, "A02", "script.write", work, project=p, needs_llm=True,
                    input_ref={"project": p.code, "idea": idea["title"], "prompt_version": label})
    data = run.output
    for s in data.get("scenes", []):
        s["dialogue"] = (s.get("dialogue") or [])[: policy["max_dialogue_lines"]]
        s["duration_sec"] = policy["scene_seconds"]
    check = _check_script(ctx, p, data)
    v = _save_version(ctx, p, script, data, source="AGENT", note=f"A02 viết từ ý tưởng #{script.selected_idea_index + 1}",
                      agent_execution_id=run.execution.id, check=check)
    sm.transition(ctx, p, "SCRIPT_REVIEW", note="Kịch bản v%d chờ duyệt" % v.version_no,
                  payload={"errors": check["errors"], "compliance": check["compliance"]})
    return v


def _save_version(ctx: Ctx, p: Project, script: Script, data: dict, *, source: str, note: str,
                  agent_execution_id=None, check: dict) -> ScriptVersion:
    scenes = _sync_scenes(ctx, p, data.get("scenes", []), note)
    v = ScriptVersion(script_id=script.id, version_no=_next_version_no(ctx, script), title=data.get("title", "")[:255],
                      hook=data.get("hook", ""), body=data.get("body", ""), cta=(data.get("cta") or "")[:255],
                      scenes=[{**_scene_snapshot(s), "order_index": s.order_index} for s in scenes], source=source,
                      change_note=note[:255], created_by=ctx.actor.user_uuid, agent_execution_id=agent_execution_id)
    ctx.db.add(v)
    ctx.db.flush()
    script.current_version_id = v.id
    script.status = "IN_REVIEW"
    script.approved_version_id = None
    audit.record(ctx, "script.version_create", "script_version", v.id,
                 after={"version": v.version_no, "source": source, "errors": len(check["errors"])})
    return v


def save_manual(ctx: Ctx, project_id, data: dict, note: str) -> ScriptVersion:
    """Chỉnh sửa thủ công → phiên bản mới (bất biến). Sửa sau khi duyệt → quay về SCRIPT_REVIEW."""
    ctx.require("script.edit")
    p = lock_project(ctx, project_id)
    if p.status not in EDITABLE_STATES:
        raise InvalidTransition(f"Không thể sửa kịch bản ở trạng thái {p.status}")
    script = get_or_create_script(ctx, p)
    check = _check_script(ctx, p, data)
    v = _save_version(ctx, p, script, data, source="HUMAN", note=note or "Chỉnh sửa thủ công", check=check)
    if p.status == "CREATED":
        sm.transition(ctx, p, "SCRIPT_GENERATING", note="Viết kịch bản thủ công")
    if p.status == "SCRIPT_GENERATING":
        sm.transition(ctx, p, "SCRIPT_REVIEW", note=f"Kịch bản v{v.version_no} (thủ công)")
    elif p.status == "STORYBOARD_READY":
        sm.transition(ctx, p, "SCRIPT_REVIEW", note="Kịch bản đã duyệt bị sửa — cần duyệt lại")
    return v


def restore_version(ctx: Ctx, project_id, version_id) -> ScriptVersion:
    ctx.require("script.edit")
    p = get_project(ctx, project_id)
    script = get_or_create_script(ctx, p)
    old = ctx.db.get(ScriptVersion, version_id)
    if old is None or old.script_id != script.id:
        raise NotFound("Không tìm thấy phiên bản")
    data = {"title": old.title, "hook": old.hook, "body": old.body, "cta": old.cta, "scenes": old.scenes}
    return save_manual(ctx, project_id, data, note=f"Khôi phục từ v{old.version_no}")


def approve_script(ctx: Ctx, project_id, comment: str = "") -> Script:
    ctx.require("script.approve")
    p = lock_project(ctx, project_id)
    if p.status != "SCRIPT_REVIEW":
        raise InvalidTransition("Kịch bản chỉ được duyệt ở trạng thái SCRIPT_REVIEW")
    script = get_or_create_script(ctx, p)
    v = ctx.db.get(ScriptVersion, script.current_version_id) if script.current_version_id else None
    if v is None:
        raise ValidationFailed("Chưa có phiên bản kịch bản")
    check = _check_script(ctx, p, {"hook": v.hook, "body": v.body, "cta": v.cta, "scenes": v.scenes})
    if check["errors"]:
        raise ValidationFailed("Kịch bản chưa đạt chuẩn storyboard", code="SCRIPT_INVALID", details=check)
    if any(f["severity"] == "CRITICAL" for f in check["compliance"]):
        raise ValidationFailed("Kịch bản vi phạm tuân thủ nghiêm trọng", code="COMPLIANCE_CRITICAL", details=check)
    script.status = "APPROVED"
    script.approved_version_id = v.id
    script.approved_by = ctx.actor.user_uuid
    script.approved_at = datetime.now(timezone.utc)
    audit.record(ctx, "script.approve", "script", script.id, after={"version": v.version_no, "comment": comment})
    sm.transition(ctx, p, "STORYBOARD_READY", note=f"Duyệt kịch bản v{v.version_no}. {comment}".strip())
    build_prompts(ctx, p.id)
    return script


def build_prompts(ctx: Ctx, project_id) -> list[Scene]:
    """A03 AI Prompt: lắp prompt 9 phần cho mọi cảnh (xác định, có log Agent)."""
    p = get_project(ctx, project_id)
    if p.status not in ("STORYBOARD_READY", "ASSET_VALIDATION", "NEEDS_MANUAL_ACTION", "SCENE_QC", "GENERATING", "GENERATION_QUEUED"):
        raise InvalidTransition("Chỉ tạo prompt sau khi kịch bản được duyệt")
    scenes = ctx.db.scalars(select(Scene).where(Scene.project_id == p.id).order_by(Scene.order_index)).all()

    def work(_llm, actx):
        built = []
        for s in scenes:
            r = prompts.build_scene_prompt(ctx, p, s)
            s.prompt_text = r["prompt_text"]
            s.prompt_parts = r["parts"]
            s.negative_prompt = r["negative_prompt"]
            s.prompt_version_id = r["prompt_version_id"]
            if s.status in ("PLANNED", "QC_FAILED"):
                s.status = "PROMPT_READY"
            built.append({"scene": s.order_index, "prompt_version": r["prompt_version_label"], "characters": r["characters_used"]})
        return {"count": len(built), "result": built}, None

    run_agent(ctx, "A03", "prompt.build", work, project=p, input_ref={"project": p.code, "scenes": len(scenes)})
    return scenes


def update_scene(ctx: Ctx, scene_id, changes: dict, note: str = "") -> Scene:
    ctx.require("script.edit")
    scene = ctx.db.get(Scene, scene_id)
    if scene is None or scene.data_mode != ctx.mode:
        raise NotFound("Không tìm thấy cảnh")
    p = lock_project(ctx, scene.project_id)
    if p.status not in EDITABLE_STATES | {"ASSET_VALIDATION", "NEEDS_MANUAL_ACTION", "SCENE_QC", "FINAL_QC"}:
        raise InvalidTransition(f"Không thể sửa cảnh ở trạng thái {p.status}")
    policy = get_setting(ctx.db, "generation.policy")
    merged = {**_scene_snapshot(scene), **changes}
    errors, warnings = validate_scenes([merged], scene_seconds=policy["scene_seconds"], max_dialogue=policy["max_dialogue_lines"])
    if errors:
        raise ValidationFailed("Cảnh không đạt chuẩn", code="SCENE_INVALID", details={"errors": errors, "warnings": warnings})
    for k, v in changes.items():
        if k in SCENE_FIELDS:
            if k == "character_ids":
                v = [str(x) for x in v or []]
            if k == "scene_lock_id" and v:
                v = uuid.UUID(str(v))
            setattr(scene, k, v)
    n = (ctx.db.scalar(select(func.max(SceneVersion.version_no)).where(SceneVersion.scene_id == scene.id)) or 0) + 1
    scene.current_version_no = n
    ctx.db.add(SceneVersion(scene_id=scene.id, version_no=n, snapshot=_scene_snapshot(scene), change_note=note[:255] or "Sửa cảnh",
                            created_by=ctx.actor.user_uuid))
    if p.status not in EDITABLE_STATES:
        r = prompts.build_scene_prompt(ctx, p, scene)
        scene.prompt_text, scene.prompt_parts, scene.negative_prompt = r["prompt_text"], r["parts"], r["negative_prompt"]
        scene.prompt_version_id = r["prompt_version_id"]
        scene.status = "PROMPT_READY"
    elif p.status == "STORYBOARD_READY":
        sm.transition(ctx, p, "SCRIPT_REVIEW", note=f"Sửa cảnh {scene.order_index + 1} — cần duyệt lại")
    audit.record(ctx, "scene.update", "scene", scene.id, after={"version": n, "fields": list(changes)})
    return scene


def script_view(ctx: Ctx, project_id) -> dict:
    p = get_project(ctx, project_id)
    script = ctx.db.scalar(select(Script).where(Script.project_id == p.id))
    versions = []
    current = None
    if script:
        versions = ctx.db.scalars(select(ScriptVersion).where(ScriptVersion.script_id == script.id)
                                  .order_by(ScriptVersion.version_no.desc())).all()
        current = next((v for v in versions if v.id == script.current_version_id), None)
    scenes = ctx.db.scalars(select(Scene).where(Scene.project_id == p.id).order_by(Scene.order_index)).all()
    check = _check_script(ctx, p, {"hook": current.hook, "body": current.body, "cta": current.cta,
                                   "scenes": current.scenes}) if current else None
    return {"project": p, "script": script, "current": current, "versions": versions, "scenes": scenes, "check": check}
