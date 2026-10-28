#!/usr/bin/env bash
# Chạy API (8000) + worker + web (3000) ở chế độ phát triển. Ctrl+C để dừng.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"; set -a; . ./.env; set +a
export PYTHONPATH="$ROOT/services/api:$ROOT/services/worker"
trap 'kill 0' EXIT
(cd services/api && ../../.venv/bin/uvicorn app.main:app --reload --port 8000) &
if [ "${CELERY_TASK_ALWAYS_EAGER:-false}" != "true" ]; then
  (cd services/worker && ../../.venv/bin/celery -A app.celery_app worker -Q generation,render,celery -l info --concurrency 2) &
  (cd services/worker && ../../.venv/bin/celery -A app.celery_app beat -l info --schedule "$ROOT/var/celerybeat-schedule") &
fi
(cd apps/web && API_PUBLIC_URL=http://localhost:8000 npm run dev) &
wait
