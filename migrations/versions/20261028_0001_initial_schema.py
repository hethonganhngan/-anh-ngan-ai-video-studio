"""initial schema (45 bảng) — DDL đóng băng tại migrations/sql/0001_initial_schema.sql

Revision ID: 0001
Revises:
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "0001_initial_schema.sql"
TABLES = ['verification_results','root_cause_analyses','lessons_learned','feedback_events','capa_actions','feedback_cases','qc_findings','approvals','analytics_snapshots','script_versions','qc_reviews','publications','cost_records','renders','agent_executions','voice_locks','system_settings','scripts','scene_versions','scene_locks','render_jobs','prompt_versions','production_batches','notifications','generation_jobs','character_references','character_locks','brand_profiles','backups','workflow_events','users','role_permissions','prompt_templates','characters','voice_profiles','scenes','roles','provider_accounts','projects','permissions','channels','budget_limits','audit_logs','assets','agent_configs']


def upgrade() -> None:
    op.execute(SQL_FILE.read_text(encoding="utf-8"))


def downgrade() -> None:
    for t in TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')
