"""vieneu_local: giọng nhân bản từ bản ghi âm chính chủ, chạy trên máy (D23)

Revision ID: 0006
Revises: 0005
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.seed.catalog import VIENEU_CONFIG

    op.get_bind().execute(
        sa.text("INSERT INTO provider_accounts (id, provider_type, provider_code, name, is_enabled, config, "
                "connection_status, unit_cost, cost_unit) VALUES (gen_random_uuid(), 'TTS', 'vieneu_local', :name, false, "
                "CAST(:cfg AS jsonb), 'NOT_CONFIGURED', 0, 'SECOND') ON CONFLICT (provider_code) DO NOTHING"),
        {"name": "VieNeu-TTS — giọng nhân bản chạy trên máy", "cfg": json.dumps(VIENEU_CONFIG, ensure_ascii=False)},
    )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM provider_accounts WHERE provider_code = 'vieneu_local'"))
