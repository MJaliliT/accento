import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from app.api.routes import detection
from app.core.config import settings


class FakeRequest:
    def __init__(self, body: bytes, content_type: str = "video/mp4"):
        self.body = body
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(body)),
        }

    async def stream(self):
        yield self.body


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def insert_one(self, document):
        self.documents.append(document)

    async def delete_one(self, _):
        return None


def test_upload_is_staged_under_random_name(monkeypatch, tmp_path):
    collection = FakeCollection()
    enqueued = []

    async def allow_quota():
        return SimpleNamespace(limit=4, remaining=3, reset_after_seconds=3600)

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(detection, "collection", collection)
    monkeypatch.setattr(detection, "enforce_daily_submission_limit", allow_quota)
    monkeypatch.setattr(detection, "enqueue_analysis", enqueued.append)

    response = Response()
    result = asyncio.run(detection.create_upload_analysis(FakeRequest(b"video-data"), response))

    assert response.status_code == 202
    assert result.status == "processing"
    assert enqueued == [result.id]
    assert (tmp_path / f"{result.id}.upload").read_bytes() == b"video-data"
    assert collection.documents[0]["source"] == "upload"
    assert "filename" not in collection.documents[0]


def test_oversized_upload_is_rejected_before_quota(monkeypatch, tmp_path):
    quota_checked = False

    async def check_quota():
        nonlocal quota_checked
        quota_checked = True

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 4)
    monkeypatch.setattr(detection, "enforce_daily_submission_limit", check_quota)

    with pytest.raises(HTTPException) as error:
        asyncio.run(detection.create_upload_analysis(FakeRequest(b"12345"), Response()))

    assert error.value.status_code == 413
    assert not quota_checked
    assert list(tmp_path.iterdir()) == []


def test_queue_failure_removes_staged_upload(monkeypatch, tmp_path):
    async def allow_quota():
        return SimpleNamespace(limit=4, remaining=3, reset_after_seconds=3600)

    def fail_to_enqueue(_):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 1024)
    monkeypatch.setattr(detection, "collection", FakeCollection())
    monkeypatch.setattr(detection, "enforce_daily_submission_limit", allow_quota)
    monkeypatch.setattr(detection, "enqueue_analysis", fail_to_enqueue)

    with pytest.raises(HTTPException) as error:
        asyncio.run(detection.create_upload_analysis(FakeRequest(b"video-data"), Response()))

    assert error.value.status_code == 503
    assert list(tmp_path.iterdir()) == []
