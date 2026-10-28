"""Hoãn gửi tác vụ Celery đến SAU khi transaction commit — worker không bao giờ đọc dữ liệu chưa commit."""
import logging

from sqlalchemy import event
from sqlalchemy.orm import Session

log = logging.getLogger("anngan.dispatch")
_KEY = "deferred_tasks"


def defer(db: Session, task_name: str, *args) -> None:
    db.info.setdefault(_KEY, []).append((task_name, args))


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    tasks = session.info.pop(_KEY, [])
    if not tasks:
        return
    from app.workflows.celery_client import enqueue

    for name, args in tasks:
        try:
            enqueue(name, *args)
        except Exception:  # broker lỗi: job vẫn QUEUED trong DB, recover_stuck_jobs sẽ gửi lại
            log.exception("enqueue failed: %s %s", name, args)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_KEY, None)
