from app.workflows.celery_client import get_celery
from app.workflows.jobs import run_render_job

celery = get_celery()


@celery.task(name="anngan.render.run_job", bind=True, acks_late=True, max_retries=0, soft_time_limit=1800, time_limit=2000)
def run_job(self, job_id: str) -> str:
    return run_render_job(job_id)
