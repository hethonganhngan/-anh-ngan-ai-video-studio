"""AgentRunner: kiểm tra phạm vi & giới hạn → chạy → ghi agent_executions + cost_records."""
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from app.agents.models import AgentConfig, AgentExecution
from app.core.context import Ctx
from app.core.errors import AppError, Forbidden, NotFound
from app.core.independent import persist
from app.core.security import decrypt_secret
from app.modules.administration import service as admin
from app.modules.administration.models import AuditLog, ProviderAccount
from app.providers.llm.base import LLMError, LLMProvider, LLMResult
from app.providers.llm.mock import MockLLMProvider
from sqlalchemy import func, select

log = logging.getLogger("anngan.agents")


class AgentScopeError(Forbidden):
    code = "AGENT_SCOPE_VIOLATION"


class AgentDisabled(AppError):
    status_code = 409
    code = "AGENT_DISABLED"


class AgentLimitExceeded(AppError):
    status_code = 429
    code = "AGENT_LIMIT_EXCEEDED"


class LLMNotConnected(AppError):
    status_code = 409
    code = "LLM_NOT_CONNECTED"


@dataclass
class AgentRun:
    execution: AgentExecution
    output: Any
    llm: LLMResult | None


def resolve_llm(ctx: Ctx, cfg: AgentConfig) -> LLMProvider:
    """DEMO → luôn Mock. PRODUCTION → provider đã cấu hình và có key; nếu không → LLMNotConnected."""
    if ctx.mode == "DEMO" or cfg.provider_code in ("mock-llm",):
        if ctx.mode == "PRODUCTION":
            raise LLMNotConnected(f"{cfg.name}: chưa cấu hình LLM thật cho PRODUCTION. Hãy thao tác thủ công, hoặc kết nối Gemini/Anthropic ở M15 rồi chọn provider tại M14.")
        return MockLLMProvider()
    if cfg.provider_code == "anthropic":
        acc = ctx.db.scalar(select(ProviderAccount).where(ProviderAccount.provider_code == "anthropic"))
        key = decrypt_secret(acc.secret_encrypted) if acc and acc.is_enabled and acc.secret_encrypted else None
        if not key:
            raise LLMNotConnected("Anthropic chưa được kết nối/bật ở M15 → API Connections")
        from app.providers.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=key, model=cfg.model)
    if cfg.provider_code == "gemini":
        acc = ctx.db.scalar(select(ProviderAccount).where(ProviderAccount.provider_code == "gemini_llm"))
        key = decrypt_secret(acc.secret_encrypted) if acc and acc.is_enabled and acc.secret_encrypted else None
        if not key:
            raise LLMNotConnected("Gemini (LLM) chưa được kết nối/bật ở M15 → API Connections")
        from app.providers.llm.gemini_provider import GeminiLLMProvider

        return GeminiLLMProvider(api_key=key, model=cfg.model, config=acc.config)
    raise LLMNotConnected(f"Provider LLM '{cfg.provider_code}' không được hỗ trợ")


def run_agent(ctx: Ctx, agent_code: str, action: str, fn: Callable[[LLMProvider | None, Ctx], tuple[Any, LLMResult | None]],
              *, project=None, input_ref: dict | None = None, needs_llm: bool = False) -> AgentRun:
    db = ctx.db
    cfg = db.get(AgentConfig, agent_code)
    if cfg is None:
        raise NotFound(f"Agent {agent_code} không tồn tại")
    if action not in (cfg.allowed_actions or []):
        persist(AuditLog(actor_type=ctx.actor.type, actor_id=ctx.actor.id, actor_label=ctx.actor.label,
                         action="agent.scope_violation", entity_type="agent", entity_id=agent_code,
                         after={"action": action}, data_mode=ctx.mode))
        raise AgentScopeError(f"{cfg.name} không được phép thực hiện '{action}'",
                              details={"agent": agent_code, "allowed": cfg.allowed_actions})
    if not cfg.is_enabled:
        raise AgentDisabled(f"{cfg.name} đang tắt")
    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    runs_today = db.scalar(select(func.count()).select_from(AgentExecution).where(
        AgentExecution.agent_code == agent_code, AgentExecution.started_at >= since, AgentExecution.data_mode == ctx.mode))
    if runs_today >= cfg.max_runs_per_day:
        raise AgentLimitExceeded(f"{cfg.name} đã đạt giới hạn {cfg.max_runs_per_day} lần chạy/ngày")

    llm = resolve_llm(ctx, cfg) if needs_llm else None
    if llm is not None and llm.is_real:
        # Chặn trước khi gọi API thật nếu chi phí tối đa của lần chạy làm vượt ngân sách
        admin.check_budget(ctx, estimated=Decimal(cfg.max_cost_per_run), project=project, provider_code=llm.code)

    agent_ctx = ctx.as_agent(agent_code, cfg.allowed_actions)
    exe_new = AgentExecution(
        id=uuid.uuid4(), agent_code=agent_code, action=action, model=getattr(llm, "model", None) or cfg.model,
        provider_code=getattr(llm, "code", None) or cfg.provider_code, project_id=project.id if project is not None else None,
        input_ref=input_ref or {}, status="RUNNING", data_mode=ctx.mode, triggered_by=ctx.actor.id,
        prompt_version_label=cfg.prompt_template_code, started_at=datetime.now(timezone.utc),
    )
    # Ghi RUNNING bằng session độc lập để log tồn tại cả khi transaction chính rollback
    persist(exe_new)
    exe_id = exe_new.id
    start = time.perf_counter()
    try:
        output, llm_result = fn(llm, agent_ctx)
    except (LLMError, AppError) as e:
        persist(_finish(exe_new, "FAILED", start, error=str(e)[:2000]))
        if isinstance(e, LLMError):
            raise AppError(f"{cfg.name} lỗi: {e}", code=e.code, status_code=502 if e.retryable else 422,
                           details={"retryable": e.retryable, "execution_id": str(exe_id)})
        raise
    except Exception as e:
        persist(_finish(exe_new, "FAILED", start, error=f"{type(e).__name__}: {e}"[:2000]))
        raise
    exe = db.get(AgentExecution, exe_id)
    if exe is None:  # ghi độc lập thất bại (ví dụ project chưa commit) → ghi trong transaction chính
        exe = exe_new
        db.add(exe)
    _finish(exe, "SUCCEEDED", start)
    if llm_result is not None:
        exe.model = llm_result.model
        exe.provider_code = llm_result.provider
        exe.input_tokens = llm_result.input_tokens
        exe.output_tokens = llm_result.output_tokens
        exe.cost = Decimal(str(llm_result.cost_vnd))
        exe.is_simulated = llm_result.simulated
        if exe.cost > 0:
            admin.record_cost(db, ctx.mode, category="LLM", provider_code=llm_result.provider, amount=exe.cost,
                              quantity=Decimal(llm_result.input_tokens + llm_result.output_tokens), unit="TOKEN",
                              project=project, agent_execution_id=exe.id, is_simulated=llm_result.simulated,
                              description=f"{agent_code} {action}")
    if isinstance(output, dict):
        exe.output_ref = {k: v for k, v in output.items() if k in ("summary", "ids", "count", "result", "score")} or {"keys": list(output)[:20]}
    db.flush()
    return AgentRun(execution=exe, output=output, llm=llm_result)


def _finish(exe: AgentExecution, status: str, start: float, error: str | None = None) -> AgentExecution:
    exe.status = status
    exe.error = error
    exe.latency_ms = int((time.perf_counter() - start) * 1000)
    exe.finished_at = datetime.now(timezone.utc)
    return exe


def sweep_abandoned(db, older_than_minutes: int = 30) -> int:
    """Đánh dấu lần chạy kẹt RUNNING (worker chết / transaction rollback) là FAILED."""
    from datetime import timedelta

    from sqlalchemy import update

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    res = db.execute(update(AgentExecution).where(AgentExecution.status == "RUNNING", AgentExecution.started_at < cutoff)
                     .values(status="FAILED", error="ABANDONED: không hoàn tất (tiến trình dừng hoặc giao dịch bị huỷ)"))
    return res.rowcount or 0
