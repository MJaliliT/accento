from fastapi import APIRouter

from app.core.cache import redis_client
from app.core.database_async import async_db as db

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
async def live():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    await db.command("ping")
    await redis_client.ping()
    return {"status": "ok"}
