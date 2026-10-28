from app.workflows.celery_client import get_celery
from app.workflows.jobs import recover_stuck_jobs

celery = get_celery()


@celery.task(name="anngan.workflow.recover_stuck")
def recover_stuck() -> dict:
    return recover_stuck_jobs(older_than_minutes=10)
