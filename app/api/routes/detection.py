import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.cache import redis_client
from app.core.config import settings
from app.core.database_async import async_collection as collection
from app.core.rate_limit import enforce_daily_submission_limit
from app.core.task_queue import enqueue_analysis
from app.schemas.detection import AnalysisResponse
from app.services.upload_service import (
    ALLOWED_UPLOAD_TYPES,
    cleanup_stale_uploads,
    delete_upload,
    upload_path_for,
)

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


def public_result(document: dict) -> AnalysisResponse:
    return AnalysisResponse(
        id=document["_id"],
        status=document["status"],
        accent=document.get("accent"),
        confidence=document.get("confidence"),
        language=document.get("language"),
        reason=document.get("reason"),
    )


@router.post("/uploads", response_model=AnalysisResponse)
async def create_upload_analysis(
    request: Request,
    response: Response,
):
    media_type = request.headers.get("content-type", "").partition(";")[0].lower()
    if media_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload an MP4, MOV, WebM, MKV, or AVI video.",
        )

    try:
        content_length = int(request.headers.get("content-length", ""))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_411_LENGTH_REQUIRED,
            detail="A valid Content-Length header is required.",
        ) from exc
    if content_length <= 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if content_length > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The maximum upload size is 25 MiB.",
        )

    quota = await enforce_daily_submission_limit()
    response.headers["X-RateLimit-Limit"] = str(quota.limit)
    response.headers["X-RateLimit-Remaining"] = str(quota.remaining)
    response.headers["X-RateLimit-Reset"] = str(quota.reset_after_seconds)

    cleanup_stale_uploads()
    analysis_id = uuid4().hex
    now = datetime.now(timezone.utc)
    document = {
        "_id": analysis_id,
        "status": "processing",
        "source": "upload",
        "content_type": media_type,
        "upload_bytes": content_length,
        "created_at": now,
        "updated_at": now,
    }

    partial_path = upload_path_for(analysis_id, partial=True)
    final_path = upload_path_for(analysis_id)
    try:
        received = 0
        with partial_path.open("xb") as destination:
            async for chunk in request.stream():
                received += len(chunk)
                if received > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="The maximum upload size is 25 MiB.",
                    )
                destination.write(chunk)

        if received == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        if received != content_length:
            raise HTTPException(status_code=400, detail="The upload was incomplete.")

        os.replace(partial_path, final_path)
        await collection.insert_one(document)
        enqueue_analysis(analysis_id)
    except HTTPException:
        delete_upload(analysis_id)
        raise
    except Exception as exc:
        delete_upload(analysis_id)
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
