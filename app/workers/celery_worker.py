from celery import Celery

from app.core.config import settings
from app.tasks.video_processing import process_video

celery = Celery(
    "accento",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)
celery.conf.update(
    task_default_queue="accento",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)


@celery.task(bind=True, name="accento.process_video", max_retries=2)
def process_video_task(self, analysis_id: str, url: str):
    try:
        return process_video(analysis_id, url)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))

        from app.tasks.video_processing import store_error

        store_error(analysis_id)
        raise
