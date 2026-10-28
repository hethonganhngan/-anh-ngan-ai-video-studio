"""Ghi audit log (append-only, được bảo vệ bằng trigger DB)."""
import decimal
import uuid
from datetime import date, datetime
from typing import Any

from app.core.context import Ctx
from app.modules.administration.models import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


def snapshot(obj: Any, fields: list[str]) -> dict:
    return _jsonable({f: getattr(obj, f, None) for f in fields})


SENSITIVE = {"password", "password_hash", "secret", "api_key", "secret_encrypted", "token"}


def _scrub(d: dict | None) -> dict | None:
    if d is None:
        return None
    return {k: ("***" if any(s in k.lower() for s in SENSITIVE) else _jsonable(v)) for k, v in d.items()}


def record(
    ctx: Ctx,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_type=ctx.actor.type,
        actor_id=ctx.actor.id,
        actor_label=ctx.actor.label,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=_scrub(before),
        after=_scrub(after),
        ip_address=ctx.ip,
        user_agent=(ctx.user_agent or "")[:255] or None,
        data_mode=ctx.mode,
    )
    ctx.db.add(log)
    return log
