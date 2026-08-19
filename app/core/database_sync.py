from pymongo import MongoClient

from app.core.config import settings

_sync_client = None


def get_collection():
    global _sync_client

    if _sync_client is None:
        _sync_client = MongoClient(settings.MONGO_URL)
    return _sync_client[settings.MONGO_DB]["analyses"]
