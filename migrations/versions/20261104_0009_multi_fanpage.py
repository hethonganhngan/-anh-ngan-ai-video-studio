"""nhiều Fanpage / kênh: bài đăng ghi Fanpage đích (publications.target_ref = page_id)

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publications", sa.Column("target_ref", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("publications", "target_ref")
