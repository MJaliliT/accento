FROM python:3.10-slim-bookworm AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=600

WORKDIR /app
RUN groupadd --system accento && useradd --system --gid accento --home /app accento
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

FROM python-base AS api
COPY --chown=accento:accento app ./app
USER accento
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

FROM python-base AS worker-deps
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-worker.txt .
RUN pip install --no-cache-dir -r requirements-worker.txt

FROM python-base AS model-builder
COPY requirements-model.txt .
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.13.0 \
    && pip install --no-cache-dir -r requirements-model.txt
ENV MODEL_OUTPUT_DIR=/models/accent_model
COPY model_Extractor.py ./
RUN python model_Extractor.py

FROM worker-deps AS whisper-builder
ENV MODEL_OUTPUT_DIR=/models/accent_model
COPY whisper_Extractor.py ./
RUN python whisper_Extractor.py

FROM worker-deps AS worker
COPY --chown=accento:accento app ./app
COPY --from=model-builder --chown=accento:accento /models/accent_model /app/app/services/accent_model
COPY --from=whisper-builder --chown=accento:accento /models/accent_model/whisper-tiny /app/app/services/accent_model/whisper-tiny
ENV HF_HOME=/tmp/huggingface \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_OFFLINE=1
USER accento
CMD ["celery", "-A", "app.workers.celery_worker:celery", "worker", "--loglevel=INFO", "--queues=accento", "--concurrency=1", "--max-tasks-per-child=20"]

FROM node:24-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.29-alpine AS web
COPY deploy/web.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /frontend/dist /usr/share/nginx/html
EXPOSE 8080
