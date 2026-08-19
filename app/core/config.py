import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME = os.getenv("APP_NAME", "accento")
    ENV = os.getenv("ENV", "development")
    DEBUG = os.getenv("DEBUG", "False") == "True"

    MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "accento")

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

    ACCENT_THRESHOLD = float(os.getenv("ACCENT_THRESHOLD", 0.6))

    TEMP_AUDIO_DIR = os.getenv("TEMP_AUDIO_DIR", "/tmp")
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/var/lib/accento/uploads")
    MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
    UPLOAD_RETENTION_SECONDS = int(os.getenv("UPLOAD_RETENTION_SECONDS", "1800"))

    DAILY_ANALYSIS_LIMIT = int(os.getenv("DAILY_ANALYSIS_LIMIT", "4"))
    RESULT_CACHE_SECONDS = int(os.getenv("RESULT_CACHE_SECONDS", "86400"))
    ERROR_CACHE_SECONDS = int(os.getenv("ERROR_CACHE_SECONDS", "300"))
    RESULT_RETENTION_DAYS = int(os.getenv("RESULT_RETENTION_DAYS", "30"))

    ALLOWED_HOSTS = [
        host.strip()
        for host in os.getenv(
            "ALLOWED_HOSTS",
            "accento.mjalili.com,localhost,127.0.0.1,testserver,api",
        ).split(",")
        if host.strip()
    ]

    SUPPORTED_ACCENTS = [
        "american",
        "british",
        "indian",
        "australian",
        "canadian",
        "irish",
        "south_african",
        "other"
    ]


settings = Settings()
