"""Gửi tác vụ sang Celery worker. Chế độ eager (test/dev không có worker) chạy đồng bộ trong tiến trình."""
import logging

from celery import Celery

from app.core.config import get_settings

log = logging.getLogger("anngan.celery")
_celery: Celery | None = None


def get_celery() -> Celery:
    global _celery
    if _celery is None:
        s = get_settings()
        _celery = Celery("anngan", broker=s.broker_url, backend=s.result_backend)
        _celery.conf.update(
            task_always_eager=s.celery_task_always_eager,
            task_eager_propagates=False,
            task_acks_late=True,
            task_reject_on_worker_lost=True,
            worker_prefetch_multiplier=1,
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            timezone="Asia/Ho_Chi_Minh",
            broker_connection_retry_on_startup=True,
            task_routes={"anngan.render.*": {"queue": "render"}, "anngan.generation.*": {"queue": "generation"}},
        )
    return _celery


def reset_celery() -> None:
    global _celery
    _celery = None


def enqueue(task_name: str, *args) -> str | None:
    """Đưa tác vụ vào hàng đợi. Eager → chạy ngay (dùng cho test & DEMO không có worker)."""
    s = get_settings()
    if s.celery_task_always_eager:
        from app.workflows.tasks_registry import run_inline

        run_inline(task_name, *args)
        return "eager"
    res = get_celery().send_task(task_name, args=list(args))
    return res.id


def worker_status() -> dict:
    s = get_settings()
    if s.celery_task_always_eager:
        return {"ok": True, "mode": "eager", "workers": 0}
    try:
        replies = get_celery().control.inspect(timeout=0.8).ping() or {}
        return {"ok": bool(replies), "mode": "celery", "workers": len(replies)}
    except Exception as e:
        return {"ok": False, "mode": "celery", "error": str(e)[:200]}
