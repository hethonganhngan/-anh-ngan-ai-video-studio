#!/usr/bin/env sh
# api | worker | beat | migrate
set -e
case "$1" in
  migrate)
    alembic upgrade head
    python -m app.seed.seed ${SEED_ARGS:-}
    ;;
  api)
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --workers "${API_WORKERS:-2}"
    ;;
  worker)
    cd /srv/services/worker
    exec celery -A app.celery_app worker -Q generation,render,celery -l info --concurrency "${WORKER_CONCURRENCY:-2}"
    ;;
  beat)
    cd /srv/services/worker
    exec celery -A app.celery_app beat -l info --schedule /srv/var/tmp/celerybeat-schedule
    ;;
  *)
    exec "$@"
    ;;
esac
