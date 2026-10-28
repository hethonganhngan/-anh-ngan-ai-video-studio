"""Ngữ cảnh thực thi dùng chung cho service: ai đang làm, ở chế độ nào."""
from dataclasses import dataclass, field

from app.core.errors import Forbidden
from sqlalchemy.orm import Session


@dataclass
class Actor:
    type: str  # USER | AGENT | SYSTEM
    id: str | None
    label: str
    permissions: set[str] = field(default_factory=set)
    role_code: str | None = None

    def has(self, perm: str) -> bool:
        return self.type == "SYSTEM" or perm in self.permissions

    @property
    def user_uuid(self):
        import uuid

        return uuid.UUID(self.id) if self.type == "USER" and self.id else None


SYSTEM_ACTOR = Actor(type="SYSTEM", id=None, label="Hệ thống")


@dataclass
class Ctx:
    db: Session
    actor: Actor
    mode: str  # DEMO | PRODUCTION
    ip: str | None = None
    user_agent: str | None = None

    def require(self, perm: str) -> None:
        if not self.actor.has(perm):
            raise Forbidden(f"Bạn không có quyền thực hiện thao tác này ({perm})", code="PERMISSION_DENIED")

    def as_agent(self, agent_code: str, allowed_actions: list[str]) -> "Ctx":
        return Ctx(
            db=self.db,
            actor=Actor(type="AGENT", id=agent_code, label=agent_code, permissions=set(allowed_actions)),
            mode=self.mode,
            ip=self.ip,
            user_agent=self.user_agent,
        )
