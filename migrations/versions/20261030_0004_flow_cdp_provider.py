"""flow_cdp: nhà cung cấp video 'Google Flow tự động (Chrome CDP, thử nghiệm)' — D21

Revision ID: 0004
Revises: 0003
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.seed.catalog import FLOW_CDP_CONFIG

    # Tắt sẵn: admin bật ở M15 sau khi chạy Chrome Flow và bấm 'Kiểm tra'
    op.get_bind().execute(
        sa.text("INSERT INTO provider_accounts (id, provider_type, provider_code, name, is_enabled, config, "
                "connection_status, unit_cost, cost_unit) VALUES (gen_random_uuid(), 'VIDEO', 'flow_cdp', :name, false, "
                "CAST(:cfg AS jsonb), 'NOT_CONFIGURED', 0, 'SECOND') ON CONFLICT (provider_code) DO NOTHING"),
        {"name": "Google Flow tự động (Chrome CDP, thử nghiệm)", "cfg": json.dumps(FLOW_CDP_CONFIG, ensure_ascii=False)},
    )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM provider_accounts WHERE provider_code = 'flow_cdp'"))
