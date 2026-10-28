"""Health, readiness, metrics (Prometheus)."""
import shutil
import time

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["Health"])

REQUESTS = Counter("anngan_http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("anngan_http_request_seconds", "HTTP latency", ["method", "route"])
STARTED = time.time()


def system_health(db: Session) -> dict:
    s = get_settings()
    checks: dict[str, dict] = {}
    try:
        db.execute(text("select 1"))
        checks["database"] = {"ok": True}
    except Exception as e:  # pragma: no cover
        checks["database"] = {"ok": False, "error": str(e)[:200]}
    try:
        import redis

        redis.Redis.from_url(s.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5).ping()
        checks["redis"] = {"ok": True}
    except Exception as e:
        checks["redis"] = {"ok": False, "error": str(e)[:200]}
    checks["ffmpeg"] = {"ok": shutil.which(s.ffmpeg_bin) is not None and shutil.which(s.ffprobe_bin) is not None}
    try:
        from app.media.storage import get_storage

        checks["storage"] = get_storage().health()
    except Exception as e:
        checks["storage"] = {"ok": False, "error": str(e)[:200]}
    try:
        from app.workflows.celery_client import worker_status

        checks["worker"] = worker_status()
    except Exception as e:
        checks["worker"] = {"ok": False, "error": str(e)[:200]}
    critical = ("database", "ffmpeg", "storage")
    return {
        "status": "ok" if all(checks[c]["ok"] for c in critical) else "degraded",
        "version": s.app_version,
        "uptime_sec": int(time.time() - STARTED),
        "checks": checks,
    }


@router.get("/health")
def health():
    return {"status": "ok", "version": get_settings().app_version}


@router.get("/health/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    data = system_health(db)
    if data["status"] != "ok":
        response.status_code = 503
    return data


@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
