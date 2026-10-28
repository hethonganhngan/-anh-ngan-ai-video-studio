from app.workflows.celery_client import get_celery
from app.workflows.jobs import poll_generation_job, run_generation_job

celery = get_celery()


@celery.task(name="anngan.generation.run_job", bind=True, acks_late=True, max_retries=0)
def run_job(self, job_id: str) -> str:
    return run_generation_job(job_id)


@celery.task(name="anngan.generation.poll_job", bind=True, acks_late=True, max_retries=0)
def poll_job(self, job_id: str) -> str:
    return poll_generation_job(job_id)
