# Accento

Accento is a public, quota-protected web application that estimates the English
accent in an uploaded video. A React frontend streams one bounded upload at a
time to a FastAPI API; Celery performs language and accent inference in the
background, with Redis for queueing/global quota enforcement and MongoDB for
short-lived results.

## Production behavior

- Single-video analysis with progress polling
- Redis-backed global limit of four submissions per UTC day
- Raw video uploads capped at 25 MiB and validated by FFmpeg in a non-root worker
- A shared 128 MiB tmpfs staging area that cannot fill the VPS disk
- Immediate deletion after processing, plus cleanup of files older than 30 minutes
- Five-second temporary audio samples, also deleted after processing
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

See [DEPLOYMENT.md](DEPLOYMENT.md) for a generic GitHub Actions, Nginx, TLS,
verification, and rollback guide. Private infrastructure identifiers such as
the VPS address, SSH username, and host keys must be stored only in GitHub
Actions secrets or the operator's local environment.
