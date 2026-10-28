"""B02 API — AI Script & Storyboard (M03)."""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require
from app.core.context import Ctx
from app.modules.projects.schemas import ProjectOut
from app.modules.scripts import service
from app.modules.scripts.schemas import SceneOut, SceneUpdate, ScriptIn, ScriptOut, ScriptVersionOut

router = APIRouter(tags=["B02 AI Script Engine"])


class IdeaSelect(BaseModel):
    index: int = Field(ge=0, le=2)


class Comment(BaseModel):
    comment: str = Field(default="", max_length=1000)


def _view(ctx: Ctx, project_id):
    v = service.script_view(ctx, project_id)
    return {
        "project": ProjectOut.model_validate(v["project"]).model_dump(mode="json"),
        "script": ScriptOut.model_validate(v["script"]).model_dump(mode="json") if v["script"] else None,
        "current": ScriptVersionOut.model_validate(v["current"]).model_dump(mode="json") if v["current"] else None,
        "versions": [ScriptVersionOut.model_validate(x).model_dump(mode="json") for x in v["versions"]],
        "scenes": [SceneOut.model_validate(s).model_dump(mode="json") for s in v["scenes"]],
        "check": v["check"],
    }


@router.get("/projects/{project_id}/script")
def get_script(project_id: uuid.UUID, ctx: Ctx = Depends(require("project.view"))):
    return _view(ctx, project_id)


@router.post("/projects/{project_id}/script/ideas")
def ideas(project_id: uuid.UUID, ctx: Ctx = Depends(require("script.generate"))):
    service.generate_ideas(ctx, project_id)
    ctx.db.commit()
    return _view(ctx, project_id)


@router.post("/projects/{project_id}/script/select-idea")
def select_idea(project_id: uuid.UUID, data: IdeaSelect, ctx: Ctx = Depends(require("script.edit"))):
    service.select_idea(ctx, project_id, data.index)
    ctx.db.commit()
    return _view(ctx, project_id)


@router.post("/projects/{project_id}/script/write")
def write(project_id: uuid.UUID, ctx: Ctx = Depends(require("script.generate"))):
    service.write_script(ctx, project_id)
    ctx.db.commit()
    return _view(ctx, project_id)


@router.put("/projects/{project_id}/script")
def save(project_id: uuid.UUID, data: ScriptIn, ctx: Ctx = Depends(require("script.edit"))):
    payload = data.model_dump(mode="json")
    note = payload.pop("note", "")
    service.save_manual(ctx, project_id, payload, note)
    ctx.db.commit()
    return _view(ctx, project_id)


@router.post("/projects/{project_id}/script/versions/{version_id}/restore")
def restore(project_id: uuid.UUID, version_id: uuid.UUID, ctx: Ctx = Depends(require("script.edit"))):
    service.restore_version(ctx, project_id, version_id)
    ctx.db.commit()
    return _view(ctx, project_id)


@router.post("/projects/{project_id}/script/approve")
def approve(project_id: uuid.UUID, data: Comment, ctx: Ctx = Depends(require("script.approve"))):
    service.approve_script(ctx, project_id, data.comment)
    ctx.db.commit()
    return _view(ctx, project_id)


@router.post("/projects/{project_id}/script/prompts")
def prompts(project_id: uuid.UUID, ctx: Ctx = Depends(require("script.edit"))):
    service.build_prompts(ctx, project_id)
    ctx.db.commit()
    return _view(ctx, project_id)


@router.patch("/scenes/{scene_id}", response_model=SceneOut)
def update_scene(scene_id: uuid.UUID, data: SceneUpdate, ctx: Ctx = Depends(require("script.edit"))):
    changes = data.model_dump(exclude_unset=True, mode="json")
    note = changes.pop("note", "")
    s = service.update_scene(ctx, scene_id, changes, note)
    ctx.db.commit()
    return s
