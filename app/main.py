from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import detection, health
from app.core.config import settings
from app.core.database_async import create_indexes

@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_indexes()
    yield


app = FastAPI(
    title="Accento API",
    docs_url=None if settings.ENV == "production" else "/docs",
    openapi_url=None if settings.ENV == "production" else "/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = request.headers.get(
        "X-Request-ID", str(uuid4())
    )
    return response

app.include_router(detection.router)
app.include_router(health.router)
