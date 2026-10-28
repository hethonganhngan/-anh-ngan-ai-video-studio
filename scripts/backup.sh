#!/usr/bin/env bash
# Sao lưu PostgreSQL (+ media local). Cron đề xuất: 0 2 * * * /path/scripts/backup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"; set -a; [ -f .env ] && . ./.env; set +a
export PYTHONPATH="$ROOT/services/api"
.venv/bin/python - <<'PY'
from app.modules.administration.backup import create_backup
import os
print(create_backup(include_media=os.environ.get("BACKUP_MEDIA", "true") == "true"))
PY
# Giữ 14 bản gần nhất
ls -1t "${BACKUP_DIR:-$ROOT/var/backups}"/anngan_* 2>/dev/null | tail -n +29 | xargs -r rm -f
