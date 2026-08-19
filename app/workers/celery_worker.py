from celery import Celery
from celery.signals import worker_ready

from app.core.config import settings
from app.core.logger import logger
from app.services.upload_service import (
    UnsupportedMedia,
    UploadMissing,
    cleanup_stale_uploads,
    delete_upload,
)
from app.tasks.video_processing import process_upload, store_error

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
    beat_schedule={
        "cleanup-stale-uploads": {
            "task": "accento.cleanup_uploads",
            "schedule": 900.0,
            "options": {"queue": "accento"},
        },
    },
    timezone="UTC",
)


@celery.task(name="accento.process_upload")
def process_upload_task(analysis_id: str):
    try:
        return process_upload(analysis_id)
    except UnsupportedMedia:
        return store_error(analysis_id, reason="unsupported_media")
    except UploadMissing:
        return store_error(analysis_id, reason="upload_expired")
    except Exception:
        logger.exception("Upload analysis failed for %s", analysis_id)
        return store_error(analysis_id)
    finally:
        delete_upload(analysis_id)


@celery.task(name="accento.cleanup_uploads")
def cleanup_uploads_task():
    return {"removed": cleanup_stale_uploads()}


@worker_ready.connect
def cleanup_uploads_on_start(**_):
    cleanup_stale_uploads()
