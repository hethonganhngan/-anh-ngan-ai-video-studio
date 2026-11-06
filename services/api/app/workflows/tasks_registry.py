"""Ánh xạ tên tác vụ → hàm thực thi. Dùng chung cho Celery worker và chế độ eager."""
import logging

log = logging.getLogger("anngan.tasks")


def _registry() -> dict:
    from app.workflows import jobs

    return {
        "anngan.generation.run_job": jobs.run_generation_job,
        "anngan.generation.poll_job": jobs.poll_generation_job,
        "anngan.render.run_job": jobs.run_render_job,
        "anngan.workflow.recover_stuck": jobs.recover_stuck_jobs,
        "anngan.publishing.auto_prepare": jobs.auto_prepare_publishing,
        "anngan.publishing.sync_facebook": jobs.sync_facebook_drafts,
    }


TASK_NAMES = ["anngan.generation.run_job", "anngan.generation.poll_job", "anngan.render.run_job", "anngan.workflow.recover_stuck",
              "anngan.publishing.auto_prepare", "anngan.publishing.sync_facebook"]


def run_inline(name: str, *args):
    fn = _registry().get(name)
    if fn is None:
        raise KeyError(f"Unknown task {name}")
    try:
        return fn(*args)
    except Exception:
        log.exception("inline task %s failed", name)
        return None
