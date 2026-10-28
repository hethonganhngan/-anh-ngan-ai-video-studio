"""Celery worker — thực thi tác vụ nền (tạo cảnh, render FFmpeg, khôi phục tác vụ kẹt).

Chạy: celery -A app.celery_app worker -Q generation,render,celery -l info
Thân tác vụ nằm ở services/api/app/workflows/jobs.py (dùng chung, idempotent)."""
import app.db.models  # noqa: F401  (nạp đủ model để SQLAlchemy phân giải khoá ngoại)
from app.core.logging import setup_logging
from app.workflows.celery_client import get_celery
from celery.schedules import crontab

setup_logging()
celery = get_celery()
celery.conf.beat_schedule = {
    "recover-stuck-jobs": {"task": "anngan.workflow.recover_stuck", "schedule": crontab(minute="*/5")},
}

import app.tasks.generation  # noqa: E402,F401
import app.tasks.maintenance  # noqa: E402,F401
import app.tasks.rendering  # noqa: E402,F401
