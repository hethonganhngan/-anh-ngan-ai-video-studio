from app.workflows.celery_client import get_celery
from app.workflows.jobs import auto_prepare_publishing, sync_facebook_drafts

celery = get_celery()


@celery.task(name="anngan.publishing.auto_prepare", acks_late=True, max_retries=0, soft_time_limit=900, time_limit=1000)
def auto_prepare(project_id: str, mode: str) -> int:
    return auto_prepare_publishing(project_id, mode)


@celery.task(name="anngan.publishing.sync_facebook")
def sync_facebook() -> dict:
    return sync_facebook_drafts()
