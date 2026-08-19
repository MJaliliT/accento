import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.core import rate_limit


class FakeRedis:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def eval(self, *args):
        self.calls.append(args)
        return self.result


def test_seconds_until_utc_midnight():
    now = datetime(2026, 8, 19, 23, 59, 30, tzinfo=timezone.utc)
    assert rate_limit.seconds_until_utc_midnight(now) == 30


def test_fourth_global_submission_is_allowed(monkeypatch):
    fake_redis = FakeRedis((4, 3600))
    monkeypatch.setattr(rate_limit, "redis_client", fake_redis)

    quota = asyncio.run(rate_limit.enforce_daily_submission_limit())

    assert quota.limit == 4
    assert quota.used == 4
    assert quota.remaining == 0
    assert fake_redis.calls[0][2].startswith("quota:analyses:")


def test_fifth_global_submission_is_rejected(monkeypatch):
    fake_redis = FakeRedis((5, 1800))
    monkeypatch.setattr(rate_limit, "redis_client", fake_redis)

    with pytest.raises(HTTPException) as error:
        asyncio.run(rate_limit.enforce_daily_submission_limit())

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "1800"
    assert error.value.headers["X-RateLimit-Remaining"] == "0"
