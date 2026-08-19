from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

from app.core.config import settings

async_client = AsyncIOMotorClient(settings.MONGO_URL)

async_db = async_client[settings.MONGO_DB]

async_collection = async_db["analyses"]


async def create_indexes():
    try:
        await async_collection.drop_index("url_1")
    except OperationFailure as exc:
        if exc.code != 27:
            raise
    await async_collection.create_index(
        "updated_at",
        expireAfterSeconds=settings.RESULT_RETENTION_DAYS * 86400,
    )
