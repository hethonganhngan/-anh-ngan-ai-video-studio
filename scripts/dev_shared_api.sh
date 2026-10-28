#!/usr/bin/env bash
# API dev dùng chung (port 8000, DB anngan_studio) ở chế độ Celery eager — để phát triển UI không cần worker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CELERY_TASK_ALWAYS_EAGER=true
export MOCK_VIDEO_WIDTH=360 MOCK_VIDEO_HEIGHT=640 OUTPUT_WIDTH=540 OUTPUT_HEIGHT=960
export CORS_ORIGINS="http://localhost:3000,http://localhost:3201,http://localhost:3202,http://localhost:3203,http://localhost:3204"
export LOGIN_RATE_LIMIT_PER_MINUTE=1000 API_RATE_LIMIT_PER_MINUTE=100000
cd "${ROOT}/services/api"
exec "${ROOT}/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning
