"""immutability triggers: approved locks / prompt versions / script versions; append-only audit logs

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

LOCK_TABLES = ["character_locks", "voice_locks", "scene_locks"]


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION an_guard_approved_lock() RETURNS trigger AS $$
        BEGIN
          IF OLD.status IN ('APPROVED','RETIRED') THEN
            IF NEW.lock_data IS DISTINCT FROM OLD.lock_data OR NEW.version_no IS DISTINCT FROM OLD.version_no THEN
              RAISE EXCEPTION 'IMMUTABLE_LOCK: % đã được duyệt, không được sửa nội dung', TG_TABLE_NAME;
            END IF;
            IF OLD.status = 'RETIRED' AND NEW.status <> 'RETIRED' THEN
              RAISE EXCEPTION 'IMMUTABLE_LOCK: bản đã RETIRED không thể kích hoạt lại';
            END IF;
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )
    for t in LOCK_TABLES:
        op.execute(f"CREATE TRIGGER trg_{t}_immutable BEFORE UPDATE ON {t} FOR EACH ROW EXECUTE FUNCTION an_guard_approved_lock();")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION an_guard_prompt_version() RETURNS trigger AS $$
        BEGIN
          IF OLD.status IN ('APPROVED','RETIRED') AND (NEW.content IS DISTINCT FROM OLD.content
             OR NEW.negative_prompt IS DISTINCT FROM OLD.negative_prompt OR NEW.rules IS DISTINCT FROM OLD.rules) THEN
            RAISE EXCEPTION 'IMMUTABLE_PROMPT: phiên bản prompt đã duyệt không được sửa';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )
    op.execute("CREATE TRIGGER trg_prompt_versions_immutable BEFORE UPDATE ON prompt_versions FOR EACH ROW EXECUTE FUNCTION an_guard_prompt_version();")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION an_guard_script_version() RETURNS trigger AS $$
        BEGIN
          IF NEW.body IS DISTINCT FROM OLD.body OR NEW.hook IS DISTINCT FROM OLD.hook OR NEW.scenes IS DISTINCT FROM OLD.scenes THEN
            RAISE EXCEPTION 'IMMUTABLE_SCRIPT_VERSION: tạo phiên bản mới thay vì sửa';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )
    op.execute("CREATE TRIGGER trg_script_versions_immutable BEFORE UPDATE ON script_versions FOR EACH ROW EXECUTE FUNCTION an_guard_script_version();")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION an_audit_append_only() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'AUDIT_APPEND_ONLY: audit_logs chỉ được ghi thêm';
        END; $$ LANGUAGE plpgsql;
        """
    )
    op.execute("CREATE TRIGGER trg_audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs FOR EACH ROW EXECUTE FUNCTION an_audit_append_only();")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS trg_script_versions_immutable ON script_versions;")
    op.execute("DROP TRIGGER IF EXISTS trg_prompt_versions_immutable ON prompt_versions;")
    for t in LOCK_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_immutable ON {t};")
    op.execute("DROP FUNCTION IF EXISTS an_audit_append_only();")
    op.execute("DROP FUNCTION IF EXISTS an_guard_script_version();")
    op.execute("DROP FUNCTION IF EXISTS an_guard_prompt_version();")
    op.execute("DROP FUNCTION IF EXISTS an_guard_approved_lock();")
