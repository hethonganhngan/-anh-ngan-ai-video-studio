"""Seed idempotent. Chạy: python -m app.seed.seed [--demo-data]

- Tạo vai trò/quyền theo app.core.permissions (đồng bộ lại mỗi lần chạy).
- Tài khoản Super Admin: INITIAL_ADMIN_EMAIL + INITIAL_ADMIN_PASSWORD; nếu không đặt, sinh mật khẩu ngẫu nhiên,
  in ra MỘT LẦN và bắt buộc đổi mật khẩu khi đăng nhập lần đầu.
- Tài khoản DEMO theo vai trò (is_demo=True) dùng DEMO_USER_PASSWORD (hoặc sinh ngẫu nhiên).
"""
import argparse
import sys
from decimal import Decimal

from app.agents.models import AgentConfig
from app.agents.registry import AGENTS, MOCK_LLM, RULE_ENGINE
from app.core.config import get_settings
from app.core.permissions import PERMISSIONS, ROLES
from app.core.security import generate_password, hash_password
from app.db.session import SessionLocal
from app.modules.administration.models import BudgetLimit, Permission, ProviderAccount, Role, SystemSetting, User
from app.modules.administration.service import DEFAULT_SETTINGS
from app.modules.projects.models import BrandProfile, Channel
from app.modules.prompts.models import PromptTemplate, PromptVersion
from app.seed.catalog import CHANNELS, DEMO_USERS, PROMPT_TEMPLATES, PROVIDERS
from sqlalchemy import select
from sqlalchemy.orm import Session


def seed_rbac(db: Session) -> dict[str, Role]:
    perms = {p.code: p for p in db.scalars(select(Permission)).all()}
    for code, desc in PERMISSIONS.items():
        if code not in perms:
            perms[code] = Permission(code=code, description=desc)
            db.add(perms[code])
        else:
            perms[code].description = desc
    db.flush()
    roles = {r.code: r for r in db.scalars(select(Role)).all()}
    for code, spec in ROLES.items():
        role = roles.get(code) or Role(code=code, name=spec["name"])
        role.name = spec["name"]
        role.permissions = [perms[p] for p in spec["permissions"]]
        db.add(role)
        roles[code] = role
    db.flush()
    return roles


def seed_users(db: Session, roles: dict[str, Role], with_demo_users: bool) -> list[tuple[str, str]]:
    s = get_settings()
    printed: list[tuple[str, str]] = []
    admin = db.scalar(select(User).where(User.email == s.initial_admin_email.lower()))
    if admin is None:
        pwd = s.initial_admin_password or generate_password()
        admin = User(email=s.initial_admin_email.lower(), full_name="CEO / Super Admin", role_id=roles["SUPER_ADMIN"].id,
                     password_hash=hash_password(pwd), must_change_password=not bool(s.initial_admin_password))
        db.add(admin)
        if not s.initial_admin_password:
            printed.append((admin.email, pwd))
    if with_demo_users:
        demo_pwd = s.demo_user_password
        generated = demo_pwd is None
        demo_pwd = demo_pwd or generate_password()
        for email, name, role in DEMO_USERS:
            if db.scalar(select(User.id).where(User.email == email)):
                continue
            db.add(User(email=email, full_name=name, role_id=roles[role].id, password_hash=hash_password(demo_pwd),
                        is_demo=True))
            if generated:
                printed.append((email, demo_pwd))
    db.flush()
    return printed


def seed_settings(db: Session) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        if db.get(SystemSetting, key) is None:
            db.add(SystemSetting(key=key, value=value))


def seed_channels(db: Session) -> None:
    for c in CHANNELS:
        ch = db.scalar(select(Channel).where(Channel.code == c["code"]))
        if ch is None:
            ch = Channel(code=c["code"], name=c["name"], description=c["description"], platforms=c["platforms"])
            db.add(ch)
            db.flush()
            db.add(BrandProfile(channel_id=ch.id, **c["brand"]))


def seed_agents(db: Session) -> None:
    for code, spec in AGENTS.items():
        cfg = db.get(AgentConfig, code)
        provider, model = MOCK_LLM if spec["uses_llm"] else RULE_ENGINE
        if cfg is None:
            cfg = AgentConfig(code=code, name=spec["name"], role_description=spec["role"], provider_code=provider,
                              model=model, allowed_actions=spec["allowed_actions"],
                              prompt_template_code=spec.get("prompt_template_code"))
            db.add(cfg)
        else:
            # Phạm vi quyền luôn đồng bộ theo mã nguồn (không cho mở rộng qua DB)
            cfg.allowed_actions = spec["allowed_actions"]
            cfg.role_description = spec["role"]


def seed_prompts(db: Session) -> None:
    for t in PROMPT_TEMPLATES:
        tpl = db.scalar(select(PromptTemplate).where(PromptTemplate.code == t["code"]))
        if tpl is not None:
            continue
        tpl = PromptTemplate(code=t["code"], name=t["name"], agent_code=t["agent_code"], purpose=t["purpose"])
        db.add(tpl)
        db.flush()
        v = PromptVersion(template_id=tpl.id, version_no=1, content=t["content"], negative_prompt=t["negative_prompt"],
                          status="APPROVED", data_mode="PRODUCTION", change_note="Phiên bản chuẩn khởi tạo")
        db.add(v)
        db.flush()
        tpl.active_version_id = v.id
        tpl.demo_active_version_id = v.id


def seed_providers(db: Session) -> None:
    for p in PROVIDERS:
        if db.scalar(select(ProviderAccount).where(ProviderAccount.provider_code == p["provider_code"])) is None:
            db.add(ProviderAccount(**{**p, "unit_cost": Decimal(p["unit_cost"])}))


def seed_budgets(db: Session) -> None:
    defaults = [("DEMO", Decimal(5_000_000)), ("PRODUCTION", Decimal(10_000_000))]
    for mode, amount in defaults:
        exists = db.scalar(select(BudgetLimit.id).where(BudgetLimit.scope == "GLOBAL", BudgetLimit.data_mode == mode))
        if not exists:
            db.add(BudgetLimit(scope="GLOBAL", scope_ref="*", period="MONTHLY", limit_amount=amount, alert_threshold_pct=80,
                               hard_stop=True, data_mode=mode))


def run(with_demo_users: bool = True, with_demo_data: bool = False) -> list[tuple[str, str]]:
    db = SessionLocal()
    try:
        roles = seed_rbac(db)
        printed = seed_users(db, roles, with_demo_users)
        seed_settings(db)
        seed_channels(db)
        seed_agents(db)
        seed_prompts(db)
        seed_providers(db)
        seed_budgets(db)
        db.commit()
        if with_demo_data:
            from app.seed.demo_data import seed_demo_data

            seed_demo_data(db)
            db.commit()
        return printed
    finally:
        db.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Seed Ánh Ngân AI Video Studio")
    ap.add_argument("--no-demo-users", action="store_true")
    ap.add_argument("--demo-data", action="store_true", help="Tạo dữ liệu mẫu DEMO (nhân vật, dự án, video mock...)")
    args = ap.parse_args(argv)
    printed = run(with_demo_users=not args.no_demo_users, with_demo_data=args.demo_data)
    print("Seed hoàn tất.")
    if printed:
        print("\n=== TÀI KHOẢN KHỞI TẠO (chỉ hiển thị MỘT LẦN — lưu vào nơi an toàn) ===", file=sys.stderr)
        for email, pwd in printed:
            print(f"  {email}  /  {pwd}", file=sys.stderr)


if __name__ == "__main__":
    main()
