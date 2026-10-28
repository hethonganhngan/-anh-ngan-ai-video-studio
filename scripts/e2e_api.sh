#!/usr/bin/env bash
# Khởi động API cho E2E: DB riêng anngan_e2e (xoá sạch), seed, Celery eager, storage tạm.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ENVIRONMENT=test
export DATABASE_URL="${E2E_DATABASE_URL:-postgresql+psycopg://anngan:anngan@localhost:5432/anngan_e2e}"
export CELERY_TASK_ALWAYS_EAGER=true
export STORAGE_LOCAL_ROOT="${ROOT}/var/e2e/storage"
export BACKUP_DIR="${ROOT}/var/e2e/backups"
export MOCK_VIDEO_WIDTH=360 MOCK_VIDEO_HEIGHT=640 OUTPUT_WIDTH=540 OUTPUT_HEIGHT=960
export SECRET_KEY="e2e-secret-key-0123456789-abcdefghijklmnopq"
export CORS_ORIGINS="http://localhost:3100,http://127.0.0.1:3100"
export INITIAL_ADMIN_EMAIL=admin@anhngan.local INITIAL_ADMIN_PASSWORD='Admin@12345678' DEMO_USER_PASSWORD='Demo@12345678'
export LOGIN_RATE_LIMIT_PER_MINUTE=1000 API_RATE_LIMIT_PER_MINUTE=100000
PY="${ROOT}/.venv/bin/python"
rm -rf "${ROOT}/var/e2e" && mkdir -p "${STORAGE_LOCAL_ROOT}" "${BACKUP_DIR}"
cd "${ROOT}/services/api"
"$PY" - <<'PYEOF'
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ["DATABASE_URL"])
with e.begin() as c:
    c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
PYEOF
"$PY" -m alembic upgrade head >/dev/null
"$PY" -m app.seed.seed >/dev/null
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8100 --log-level warning
