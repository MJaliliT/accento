# Accento

Accento is a public, quota-protected web application that estimates the English
accent spoken in a public YouTube video. A React frontend submits one video at a
time to a FastAPI API; Celery performs language and accent inference in the
background, with Redis for queueing/global quota enforcement and MongoDB for short-lived
results.

## Production behavior

- Single-video analysis with progress polling
- Redis-backed global limit of four submissions per UTC day
- Strict YouTube URL allowlist and normalization
- Five-second temporary audio samples, deleted after processing
- Results expire from MongoDB after 30 days
- Same-origin API with no public database, cache, or worker ports
- Immutable Git-SHA container deployments through GitHub Actions

## Local development

The complete Docker development stack includes the embedded ML model and can
take time to build the first time:

```bash
docker compose up --build
```

Open `http://localhost:8080`. The local stack uses the same four-per-day global
quota as production; restart or clear Redis to reset it during development.

For frontend-only work:

```bash
cd frontend
npm install
npm run dev
```

For backend unit tests:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the exact Hostinger DNS, GitHub Actions,
Nginx, TLS, verification, and rollback steps for
`accento.mjalili.com`.
