"""flow_cdp: gắn nhân vật + ảnh cửa hàng (chip @) và tắt tiếng gốc khi lồng giọng M04

Revision ID: 0005
Revises: 0004
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

ADD = {"voiceover_scene_volume": 0.0, "ingredients": ["Mẹ Ánh Ngân", "Cửa hàng Ánh Ngân"]}


def upgrade() -> None:
    # ADD || config: chỉ bổ sung khoá còn thiếu, giữ nguyên giá trị người dùng đã chỉnh
    op.get_bind().execute(
        sa.text("UPDATE provider_accounts SET config = CAST(:add AS jsonb) || config WHERE provider_code = 'flow_cdp'"),
        {"add": json.dumps(ADD, ensure_ascii=False)},
    )


def downgrade() -> None:
    pass
