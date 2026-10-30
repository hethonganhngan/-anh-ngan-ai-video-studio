"""M14 — AI Agent Control Center."""
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.agents.models import AgentConfig, AgentExecution, AgentSkill
from app.agents.registry import AGENTS
from app.agents.runner import sweep_abandoned
from app.api.deps import require
from app.api.schemas import ORM, Page
from app.core import audit
from app.core.context import Ctx
from app.core.errors import NotFound, ValidationFailed
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select

router = APIRouter(prefix="/agents", tags=["M14 AI Agent Control Center"])
LLM_PROVIDERS = {"mock-llm": ["mock-deterministic-v1"], "anthropic": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
                 "gemini": ["gemini-3.8-flash", "gemini-4-argon", "gemini-3.5-flash-lite"]}


class ExecOut(ORM):
    id: str | None = None
    agent_code: str
    action: str
    model: str
    provider_code: str
    prompt_version_label: str | None
    project_id: object | None
    input_ref: dict
    output_ref: dict
    input_tokens: int
    output_tokens: int
    cost: Decimal
    is_simulated: bool
    latency_ms: int
    status: str
    error: str | None
    triggered_by: str | None
    started_at: datetime
    finished_at: datetime | None


class AgentPatch(BaseModel):
    is_enabled: bool | None = None
    max_runs_per_day: int | None = Field(default=None, ge=1, le=100000)
    max_cost_per_run: Decimal | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, ge=256, le=128000)
    timeout_sec: int | None = Field(default=None, ge=5, le=3600)
    provider_code: str | None = None
    model: str | None = None


def _stats(ctx: Ctx, code: str, since: datetime) -> dict:
    q = select(func.count(), func.coalesce(func.sum(AgentExecution.input_tokens + AgentExecution.output_tokens), 0),
               func.coalesce(func.sum(AgentExecution.cost), 0), func.coalesce(func.avg(AgentExecution.latency_ms), 0),
               func.count().filter(AgentExecution.status == "FAILED")).where(
        AgentExecution.agent_code == code, AgentExecution.data_mode == ctx.mode, AgentExecution.started_at >= since)
    runs, tokens, cost, lat, errors = ctx.db.execute(q).one()
    last = ctx.db.scalar(select(AgentExecution.started_at).where(AgentExecution.agent_code == code,
                                                                 AgentExecution.data_mode == ctx.mode)
                         .order_by(AgentExecution.started_at.desc()).limit(1))
    return {"runs": runs, "tokens": int(tokens), "cost": float(cost), "avg_latency_ms": int(lat), "errors": errors,
            "error_rate": round(errors / runs * 100, 1) if runs else 0, "last_run_at": last.isoformat() if last else None}


def _agent(ctx: Ctx, cfg: AgentConfig, since) -> dict:
    spec = AGENTS.get(cfg.code, {})
    return {"code": cfg.code, "name": cfg.name, "role": cfg.role_description, "uses_llm": spec.get("uses_llm", False),
            "provider_code": cfg.provider_code, "model": cfg.model, "is_enabled": cfg.is_enabled,
            "allowed_actions": cfg.allowed_actions, "prompt_template_code": cfg.prompt_template_code,
            "max_runs_per_day": cfg.max_runs_per_day, "max_cost_per_run": float(cfg.max_cost_per_run),
            "max_tokens": cfg.max_tokens, "timeout_sec": cfg.timeout_sec, "stats": _stats(ctx, cfg.code, since),
            "status": "DISABLED" if not cfg.is_enabled else "ACTIVE"}


@router.get("")
def list_agents(days: int = Query(30, ge=1, le=365), ctx: Ctx = Depends(require("agent.view"))):
    sweep_abandoned(ctx.db)
    ctx.db.commit()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return [_agent(ctx, c, since) for c in ctx.db.scalars(select(AgentConfig).order_by(AgentConfig.code)).all()]


@router.get("/executions", response_model=Page[ExecOut])
def executions(agent_code: str | None = None, status: str | None = None, project_id: str | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(50, le=200), ctx: Ctx = Depends(require("agent.view"))):
    q = select(AgentExecution).where(AgentExecution.data_mode == ctx.mode)
    if agent_code:
        q = q.where(AgentExecution.agent_code == agent_code)
    if status:
        q = q.where(AgentExecution.status == status)
    if project_id:
        q = q.where(AgentExecution.project_id == project_id)
    total = ctx.db.scalar(select(func.count()).select_from(q.subquery()))
    rows = ctx.db.scalars(q.order_by(AgentExecution.started_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = [ExecOut.model_validate({**{c.name: getattr(r, c.name) for c in AgentExecution.__table__.columns},
                                     "id": str(r.id), "project_id": str(r.project_id) if r.project_id else None}) for r in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)


# ---------- Skills: gói hướng dẫn cắm vào agent dùng LLM, bật/tắt từng skill ----------
MAX_SKILL_CONTENT = 60000
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)


class SkillIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    content: str = Field(min_length=10, max_length=MAX_SKILL_CONTENT)
    agent_codes: list[str] = Field(default_factory=list)
    is_enabled: bool = True
    sort_order: int = Field(default=100, ge=0, le=10000)


class SkillPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    content: str | None = Field(default=None, min_length=10, max_length=MAX_SKILL_CONTENT)
    agent_codes: list[str] | None = None
    is_enabled: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)


def _skill(s: AgentSkill) -> dict:
    return {"id": str(s.id), "code": s.code, "name": s.name, "description": s.description, "content": s.content,
            "agent_codes": s.agent_codes or [], "is_enabled": s.is_enabled, "source": s.source, "sort_order": s.sort_order,
            "chars": len(s.content), "updated_at": s.updated_at.isoformat() if s.updated_at else None}


def _check_agents(codes: list[str]) -> list[str]:
    bad = [c for c in codes if not AGENTS.get(c, {}).get("uses_llm")]
    if bad:
        raise ValidationFailed(f"Chỉ cắm skill vào agent dùng LLM; {', '.join(bad)} là rule-engine hoặc không tồn tại",
                               code="SKILL_AGENT_NOT_LLM")
    return sorted(set(codes))


def _slug(name: str, db) -> str:
    base = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:60] or "skill"
    code, n = base, 2
    while db.scalar(select(AgentSkill.id).where(AgentSkill.code == code)):
        code, n = f"{base}-{n}", n + 1
    return code


def parse_skill_md(text: str, filename: str = "") -> dict:
    """SKILL.md: frontmatter YAML (name, description) + nội dung; không có frontmatter → tên theo tên file."""
    meta, body = {}, text
    m = FRONTMATTER.match(text)
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(":")
            if sep and k.strip() in ("name", "description"):
                meta[k.strip()] = v.strip().strip("'\"")
    name = meta.get("name") or re.sub(r"\.(md|markdown|txt)$", "", filename or "", flags=re.I) or "Skill"
    return {"name": name[:160], "description": meta.get("description", "")[:2000], "content": body.strip()}


def _get_skill(ctx: Ctx, skill_id: uuid.UUID) -> AgentSkill:
    s = ctx.db.get(AgentSkill, skill_id)
    if s is None:
        raise NotFound("Không tìm thấy skill")
    return s


@router.get("/skills")
def list_skills(ctx: Ctx = Depends(require("agent.view"))):
    rows = ctx.db.scalars(select(AgentSkill).order_by(AgentSkill.sort_order, AgentSkill.name)).all()
    return [_skill(s) for s in rows]


@router.post("/skills", status_code=201)
def create_skill(data: SkillIn, ctx: Ctx = Depends(require("agent.manage"))):
    s = AgentSkill(code=_slug(data.name, ctx.db), name=data.name.strip(), description=data.description.strip(),
                   content=data.content.strip(), agent_codes=_check_agents(data.agent_codes), is_enabled=data.is_enabled,
                   sort_order=data.sort_order, source="MANUAL")
    ctx.db.add(s)
    ctx.db.flush()
    audit.record(ctx, "agent.skill_create", "agent_skill", s.id, after={"code": s.code, "agents": s.agent_codes})
    ctx.db.commit()
    return _skill(s)


@router.post("/skills/import", status_code=201)
async def import_skill(file: UploadFile = File(...), agent_codes: str = Form(""),
                       ctx: Ctx = Depends(require("agent.manage"))):
    raw = await file.read(MAX_SKILL_CONTENT * 4 + 1)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationFailed("File skill phải là văn bản UTF-8 (.md)", code="SKILL_NOT_TEXT")
    parsed = parse_skill_md(text, file.filename or "")
    data = SkillIn(**parsed, agent_codes=[c for c in agent_codes.split(",") if c.strip()])
    s = AgentSkill(code=_slug(data.name, ctx.db), name=data.name, description=data.description, content=data.content,
                   agent_codes=_check_agents([c.strip() for c in data.agent_codes]), is_enabled=True, source="UPLOAD")
    ctx.db.add(s)
    ctx.db.flush()
    audit.record(ctx, "agent.skill_import", "agent_skill", s.id, after={"code": s.code, "file": file.filename})
    ctx.db.commit()
    return _skill(s)


@router.patch("/skills/{skill_id}")
def update_skill(skill_id: uuid.UUID, data: SkillPatch, ctx: Ctx = Depends(require("agent.manage"))):
    s = _get_skill(ctx, skill_id)
    ch = data.model_dump(exclude_unset=True)
    if "agent_codes" in ch:
        ch["agent_codes"] = _check_agents(ch["agent_codes"] or [])
    before = {k: getattr(s, k) for k in ch if k != "content"}
    for k, v in ch.items():
        setattr(s, k, v.strip() if isinstance(v, str) else v)
    audit.record(ctx, "agent.skill_update", "agent_skill", s.id, before=before,
                 after={k: v for k, v in ch.items() if k != "content"} | ({"content_chars": len(s.content)} if "content" in ch else {}))
    ctx.db.commit()
    return _skill(s)


@router.delete("/skills/{skill_id}", status_code=204)
def delete_skill(skill_id: uuid.UUID, ctx: Ctx = Depends(require("agent.manage"))):
    s = _get_skill(ctx, skill_id)
    audit.record(ctx, "agent.skill_delete", "agent_skill", s.id, before={"code": s.code, "agents": s.agent_codes})
    ctx.db.delete(s)
    ctx.db.commit()


@router.get("/{code}")
def get_agent(code: str, ctx: Ctx = Depends(require("agent.view"))):
    cfg = ctx.db.get(AgentConfig, code)
    if cfg is None:
        raise NotFound("Không tìm thấy Agent")
    return _agent(ctx, cfg, datetime.now(timezone.utc) - timedelta(days=30))


@router.patch("/{code}")
def update_agent(code: str, data: AgentPatch, ctx: Ctx = Depends(require("agent.manage"))):
    cfg = ctx.db.get(AgentConfig, code)
    if cfg is None:
        raise NotFound("Không tìm thấy Agent")
    ch = data.model_dump(exclude_unset=True)
    if "provider_code" in ch or "model" in ch:
        if not AGENTS[code]["uses_llm"]:
            raise ValidationFailed(f"{cfg.name} là rule-engine (phép tính xác định) — không dùng LLM")
        prov = ch.get("provider_code", cfg.provider_code)
        model = ch.get("model", cfg.model if prov == cfg.provider_code else LLM_PROVIDERS.get(prov, [""])[0])
        if prov not in LLM_PROVIDERS or model not in LLM_PROVIDERS[prov]:
            raise ValidationFailed("Provider/model không được hỗ trợ")
        ch["provider_code"], ch["model"] = prov, model
    before = {k: getattr(cfg, k) for k in ch}
    for k, v in ch.items():
        setattr(cfg, k, v)
    audit.record(ctx, "agent.update", "agent", code, before=before, after=ch)
    ctx.db.commit()
    return _agent(ctx, cfg, datetime.now(timezone.utc) - timedelta(days=30))
