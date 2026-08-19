import json
import os
import shutil
from datetime import datetime, timezone

from app.core.cache_sync import redis_client_sync
from app.core.config import settings
from app.core.database_sync import collection
from app.core.logger import logger
from app.services.accent_service import detect_accent
from app.services.language_service import detect_language
from app.services.youtube_service import download_audio, get_video_info


def cache_result(analysis_id: str, result: dict, ttl: int) -> None:
    public_result = {"id": analysis_id, **result}
    redis_client_sync.set(
        f"analysis:{analysis_id}",
        json.dumps(public_result),
        ex=ttl,
    )


def store_result(analysis_id: str, result: dict) -> dict:
    collection.update_one(
        {"_id": analysis_id},
        {"$set": {**result, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    cache_result(analysis_id, result, settings.RESULT_CACHE_SECONDS)
    return result


def store_error(analysis_id: str, reason: str = "processing_failed") -> dict:
    result = {
        "status": "error",
        "accent": None,
        "confidence": None,
        "language": None,
        "reason": reason,
    }
    collection.update_one(
        {"_id": analysis_id},
        {"$set": {**result, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    cache_result(analysis_id, result, settings.ERROR_CACHE_SECONDS)
    return result


def process_video(analysis_id: str, url: str):
    logger.info("Processing analysis %s", analysis_id)

    cached = redis_client_sync.get(f"analysis:{analysis_id}")
    if cached:
        return json.loads(cached)

    db_result = collection.find_one({"_id": analysis_id})
    if db_result and db_result.get("status") == "done":
        result = {
            key: db_result.get(key)
            for key in ("status", "accent", "confidence", "language", "reason")
        }
        cache_result(analysis_id, result, settings.RESULT_CACHE_SECONDS)
        return result

    audio_path = None
    try:
        info = get_video_info(url)
        if info["is_live"] or info["live_status"] == "is_live":
            return store_result(analysis_id, {
                "status": "done",
                "accent": None,
                "confidence": None,
                "language": None,
                "reason": "live_stream_skipped",
            })

        audio_path = download_audio(url)
        language = detect_language(audio_path).lower()
        logger.info("Detected language for %s: %s", analysis_id, language)

        if language != "en":
            return store_result(analysis_id, {
                "status": "done",
                "accent": None,
                "confidence": None,
                "language": language,
                "reason": "non_english",
            })

        accent, confidence, _ = detect_accent(audio_path)
        return store_result(analysis_id, {
            "status": "done",
            "accent": accent,
            "confidence": confidence,
            "language": language,
            "reason": None,
        })
    finally:
        if audio_path:
            shutil.rmtree(os.path.dirname(audio_path), ignore_errors=True)
