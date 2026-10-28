#!/usr/bin/env bash
# Chạy toàn bộ kiểm thử: lint + unit + integration (pytest) + typecheck/build web + E2E Playwright.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "== Ruff =="; .venv/bin/ruff check services tests
echo "== Pytest (unit + integration) =="; .venv/bin/python -m pytest -q -p no:warnings
echo "== Web typecheck + build =="; (cd apps/web && npx tsc --noEmit && NEXT_TELEMETRY_DISABLED=1 npx next build >/dev/null && echo build OK)
echo "== E2E Playwright (15 màn hình) =="; (cd tests/e2e && npx playwright test)
