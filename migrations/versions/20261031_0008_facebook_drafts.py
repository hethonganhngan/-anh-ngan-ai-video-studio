"""facebook drafts: kênh gắn Fanpage (channels.publish_targets), bài đăng lưu mã video trên nền tảng (publications.external_id)

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channels", sa.Column("publish_targets", postgresql.JSONB(astext_type=sa.Text()),
                                        server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("publications", sa.Column("external_id", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("publications", "external_id")
    op.drop_column("channels", "publish_targets")
