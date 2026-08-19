import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status
from pymongo.errors import DuplicateKeyError

from app.core.cache import redis_client
from app.core.database_async import async_collection as collection
from app.core.rate_limit import enforce_daily_submission_limit
from app.core.task_queue import enqueue_analysis
from app.schemas.detection import AnalysisRequest, AnalysisResponse
from app.services.url_service import InvalidYouTubeUrl, normalize_youtube_url

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def analysis_id_for(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def public_result(document: dict) -> AnalysisResponse:
    return AnalysisResponse(
        id=document["_id"],
        status=document["status"],
        accent=document.get("accent"),
        confidence=document.get("confidence"),
        language=document.get("language"),
        reason=document.get("reason"),
    )


@router.post("", response_model=AnalysisResponse)
async def create_analysis(
    payload: AnalysisRequest,
    response: Response,
):
    try:
        url = normalize_youtube_url(str(payload.url))
    except InvalidYouTubeUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    quota = await enforce_daily_submission_limit()
    response.headers["X-RateLimit-Limit"] = str(quota.limit)
    response.headers["X-RateLimit-Remaining"] = str(quota.remaining)
    response.headers["X-RateLimit-Reset"] = str(quota.reset_after_seconds)

    analysis_id = analysis_id_for(url)
    existing = await collection.find_one({"_id": analysis_id})
    if existing:
        if existing.get("status") == "error":
            now = datetime.now(timezone.utc)
            await collection.update_one(
                {"_id": analysis_id, "status": "error"},
                {"$set": {
                    "status": "processing",
                    "accent": None,
                    "confidence": None,
                    "language": None,
                    "reason": None,
                    "updated_at": now,
                }},
            )
            try:
                enqueue_analysis(analysis_id, url)
            except Exception as exc:
                await collection.update_one(
                    {"_id": analysis_id, "status": "processing"},
                    {"$set": {
                        "status": "error",
                        "reason": "queue_unavailable",
                        "updated_at": datetime.now(timezone.utc),
                    }},
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The analysis queue is temporarily unavailable.",
                ) from exc
            await redis_client.delete(f"analysis:{analysis_id}")
            existing.update({
                "status": "processing",
                "accent": None,
                "confidence": None,
                "language": None,
                "reason": None,
                "updated_at": now,
            })
            response.status_code = status.HTTP_202_ACCEPTED
        return public_result(existing)

    now = datetime.now(timezone.utc)
    document = {
        "_id": analysis_id,
        "url": url,
        "status": "processing",
        "created_at": now,
        "updated_at": now,
    }

    try:
        await collection.insert_one(document)
        enqueue_analysis(analysis_id, url)
    except DuplicateKeyError:
        document = await collection.find_one({"_id": analysis_id}) or document
    except Exception as exc:
        await collection.delete_one({"_id": analysis_id, "status": "processing"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The analysis queue is temporarily unavailable.",
        ) from exc

    response.status_code = status.HTTP_202_ACCEPTED
    response.headers["Location"] = f"/api/analyses/{analysis_id}"
    return public_result(document)


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(analysis_id: str):
    if not valid_analysis_id(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found.")

    cached = await redis_client.get(f"analysis:{analysis_id}")
    if cached:
        return AnalysisResponse.model_validate(json.loads(cached))

    document = await collection.find_one({"_id": analysis_id})
    if not document:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return public_result(document)


def valid_analysis_id(value: str) -> bool:
    return len(value) == 32 and all(char in "0123456789abcdef" for char in value)
