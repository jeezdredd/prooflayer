# ProofLayer

Multi-modal content verification platform. Detects deepfakes, AI-generated images, manipulated media, tracks provenance, and fact-checks textual claims.

Backend is Django + Celery, frontend is React + Vite. Uses Postgres, Redis, MinIO (S3-compatible) and a self-hosted Ollama instance for LLM inference.

## Features

- 7 analyzers running in parallel via Celery `chord`:
  - `metadata` reads EXIF/XMP, flags edit-software signatures
  - `ela` Error Level Analysis for splice/clone detection
  - `clip_detector` CLIP zero-shot classification for AI-generated images
  - `llm_text` qwen2.5:3b on Ollama for text classification
  - `llm_vision` moondream on Ollama for image scene reasoning
  - `audio` librosa spectral features for synthetic-voice detection
  - `video` frame sampling with per-frame ELA + CLIP
- Provenance via perceptual hashes (pHash, dHash, aHash) against a known-fake database, with optional reverse search hooks (TinEye, Google Vision)
- Fact-checking: spaCy NER for claim extraction, DuckDuckGo for context, Google Fact Check API for cross-reference
- Crowdsource voting (real / fake / uncertain) per submission
- User reports backed by a moderation queue in Django admin
- SHA-256 result caching: re-uploading the same file returns the prior verdict instantly
- WeasyPrint PDF reports
- Embeddable JS badge for third-party sites
- Filtered, paginated dashboard
- JWT auth with refresh rotation
- OpenAPI schema at `/api/docs/`

## Stack

Backend: Django 5.1, DRF 3.15, Celery 5.4, PostgreSQL 16, Redis 7, MinIO, Ollama, WeasyPrint 57.2, transformers + torch (CPU), librosa, OpenCV, Pillow, imagehash, spaCy.

Frontend: React 18, Vite 6, TypeScript 5.6, Tailwind 3, Zustand 5, TanStack Query 5, React Router 7, Axios.

Infra: Docker Compose for local, Railway for production, Sentry for errors, Flower for Celery monitoring, GitHub Actions for CI.

## Architecture

```
              [ React SPA ]
              (Vite, Nginx)
                    |
                    | HTTPS, JWT
                    v
              [ Django API ]  <----->  [ Postgres ]
              (gunicorn)
                    |
                    | publish
                    v
              [ Redis broker ]
                    |
                    v
            [ Celery worker ]  <----->  [ MinIO (S3) ]
            (queues: default, ml, reports)
                    |
                    v
              [ Ollama ]
        qwen2.5:3b + moondream
```

Pipeline:

1. Client uploads a file. Django writes it to MinIO and creates a `Submission` row.
2. `process_submission` is queued. SHA-256 and perceptual hashes are computed.
3. Cache lookup: if a completed submission with the same SHA exists, results are cloned and the task returns.
4. Otherwise a chord of analyzer tasks runs on the `ml` queue.
5. The `aggregate_results` callback computes a weighted final score and verdict.
6. Provenance and factcheck tasks run on the `default` queue.
7. The frontend polls `/api/v1/content/submissions/<id>/` and renders the result page.

## Local development

Requires Docker and Docker Compose.

```bash
git clone <repo>
cd prooflayer
docker-compose up --build
```

First boot pulls Ollama models (~5 GB). Wait for `ollama_init` to exit before submitting LLM-dependent uploads.

| Service     | URL                              | Notes                          |
|-------------|----------------------------------|--------------------------------|
| Frontend    | http://localhost:5173            | Vite dev server                |
| Backend API | http://localhost:8000/api/v1     | Django + DRF                   |
| Swagger     | http://localhost:8000/api/docs/  | OpenAPI explorer               |
| Admin       | http://localhost:8000/admin/     | Requires superuser             |
| Flower      | http://localhost:5555            | Celery monitor                 |
| MinIO       | http://localhost:9001            | Console (minioadmin/minioadmin)|
| Ollama      | http://localhost:11434           | LLM API                        |

Create a superuser:

```bash
docker-compose exec backend python manage.py createsuperuser
```

Run tests:

```bash
docker-compose exec backend pytest
```

## Environment variables

Backend:

| Variable                  | Default                    | Purpose                       |
|---------------------------|----------------------------|-------------------------------|
| `SECRET_KEY`              | insecure-dev-key           | Django secret                 |
| `DATABASE_URL`            | (none)                     | Postgres DSN                  |
| `REDIS_URL`               | redis://localhost:6379/0   | Cache and broker              |
| `CELERY_BROKER_URL`       | redis://localhost:6379/0   | Celery broker                 |
| `OLLAMA_URL`              | http://ollama:11434        | Ollama endpoint               |
| `OLLAMA_MODEL`            | qwen2.5:3b                 | Text LLM                      |
| `OLLAMA_VISION_MODEL`     | moondream                  | Vision LLM (must be pulled)   |
| `AWS_ACCESS_KEY_ID`       | (none)                     | MinIO/S3 key                  |
| `AWS_SECRET_ACCESS_KEY`   | (none)                     | MinIO/S3 secret               |
| `AWS_STORAGE_BUCKET_NAME` | prooflayer-media           | Bucket name                   |
| `AWS_S3_ENDPOINT_URL`     | http://minio:9000          | MinIO endpoint                |
| `SENTRY_DSN`              | (none)                     | Optional error tracking       |
| `TINEYE_API_KEY`          | (none)                     | Optional reverse search       |
| `GOOGLE_FACT_CHECK_KEY`   | (none)                     | Optional fact-check API       |

Frontend (`frontend/.env.local`, copy from `.env.example`):

```
VITE_API_URL=http://localhost:8000/api/v1
```

## Project layout

```
backend/
  analyzers/     # 7 analyzer implementations, registry, Celery tasks
  content/       # Submission model, upload, pipeline, PDF report, widget endpoint
  crowdsource/   # Vote model and endpoints
  reports/       # User report (moderation) model and endpoints
  provenance/    # Perceptual hash matching, reverse search hooks
  factcheck/     # Claim extraction (spaCy NER) and cross-reference
  users/         # Custom User model and JWT auth
  config/        # Settings (base/dev/prod), Celery app, URLs
  templates/     # WeasyPrint PDF report template
frontend/
  src/
    pages/       # Landing, Login, Register, Upload, Dashboard, Result, FactCheck, CommunityFakes
    components/  # Layout, VotingPanel, ReportButton, SubmissionTable, etc.
    hooks/       # React Query hooks per resource
    api/         # Axios client and endpoints
    stores/      # Zustand auth store
    types/       # Shared TS interfaces
  public/
    widget.js    # Embeddable badge script
worker/          # Optional standalone Celery container config
```

## Production deployment (Railway)

Each service is a separate Railway app pointing at this repo. Service configs live in `backend/railway.toml` and `frontend/railway.toml`.

Backend service. Root `.`, Dockerfile `backend/Dockerfile`. Migrations and `seed_analyzers` run on boot.

Celery service. Same image, override start command:

```
celery -A config.celery worker --loglevel=info -Q default,ml,reports --concurrency=2
```

Ollama service. Image `ollama/ollama:latest`. A persistent volume mounted at `/root/.ollama` is required (10 GB), otherwise models redownload on every deploy. Start command:

```
sh -c "ollama serve & sleep 8 && ollama pull qwen2.5:3b && ollama pull moondream && wait"
```

Without the pull, `/api/generate` returns 404 for the vision model and `llm_vision` falls back to inconclusive.

MinIO service. `minio/minio:latest`, volume at `/data`, port 9000 exposed internally.

Postgres and Redis are Railway templates wired through `DATABASE_URL` and `REDIS_URL`.

Required on both backend and celery services:

```
OLLAMA_URL=http://ollama.railway.internal:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_VISION_MODEL=moondream
```

Frontend service. Root `frontend`, Dockerfile `frontend/Dockerfile`. Nginx serves the built static bundle and reverse-proxies `/api/` to the backend.

## Tests

```bash
pytest backend/                  # all tests
pytest backend/content/tests/    # one app
pytest -k test_caching           # filter by keyword
```

Test settings module is `config.settings.dev` (configured in `pyproject.toml`).

## License

MIT.
