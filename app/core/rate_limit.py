from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException, status

from app.core.cache import redis_client
from app.core.config import settings


_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


@dataclass(frozen=True)
class DailyQuota:
    limit: int
    used: int
    remaining: int
    reset_after_seconds: int


def seconds_until_utc_midnight(now: datetime | None = None) -> int:
    current = now or datetime.now(timezone.utc)
    tomorrow = current.date() + timedelta(days=1)
    reset_at = datetime.combine(tomorrow, time.min, tzinfo=timezone.utc)
    return max(int((reset_at - current).total_seconds()), 1)


async def enforce_daily_submission_limit() -> DailyQuota:
    now = datetime.now(timezone.utc)
    key = f"quota:analyses:{now.date().isoformat()}"
    reset_after = seconds_until_utc_midnight(now)
    count, ttl = await redis_client.eval(
        _RATE_LIMIT_SCRIPT,
        1,
        key,
        reset_after,
    )

    used = int(count)
    retry_after = max(int(ttl), 1)
    quota = DailyQuota(
        limit=settings.DAILY_ANALYSIS_LIMIT,
        used=used,
        remaining=max(settings.DAILY_ANALYSIS_LIMIT - used, 0),
        reset_after_seconds=retry_after,
    )
    if used > settings.DAILY_ANALYSIS_LIMIT:
        retry_after = max(int(ttl), 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"The global daily limit of {settings.DAILY_ANALYSIS_LIMIT} analyses "
                "has been reached. Try again after 00:00 UTC."
            ),
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(settings.DAILY_ANALYSIS_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(retry_after),
            },
        )
    return quota
