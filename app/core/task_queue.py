from celery import Celery

from app.core.config import settings


celery_client = Celery(
    "accento-client",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)


def enqueue_analysis(analysis_id: str) -> None:
    celery_client.send_task(
        "accento.process_upload",
        args=[analysis_id],
        queue="accento",
    )
