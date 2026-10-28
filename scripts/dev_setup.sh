#!/usr/bin/env bash
# Cài đặt môi trường phát triển (không Docker): venv Python, npm, DB, migration, seed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
for bin in python3 node npm ffmpeg ffprobe psql redis-cli; do
  command -v "$bin" >/dev/null || { echo "Thiếu $bin — xem docs/deployment/INSTALL.md"; exit 1; }
done
[ -f .env ] || { cp .env.example .env; echo "Đã tạo .env từ .env.example — hãy sửa các giá trị CHANGE_ME"; }
python3 -m venv .venv
.venv/bin/pip install -q -r services/api/requirements-dev.txt
(cd apps/web && npm ci --no-audit --no-fund)
(cd tests/e2e && npm ci --no-audit --no-fund)
set -a; . ./.env; set +a
(cd services/api && ../../.venv/bin/alembic upgrade head && ../../.venv/bin/python -m app.seed.seed)
echo "Xong. Chạy: scripts/dev_run.sh"
