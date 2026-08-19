from pymongo import MongoClient

from app.core.config import settings

sync_client = MongoClient(settings.MONGO_URL)

sync_db = sync_client[settings.MONGO_DB]

collection = sync_db["analyses"]
