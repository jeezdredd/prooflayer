# ProofLayer

Multi-modal content verification platform. Detects deepfakes, AI-generated images, manipulated media, tracks provenance, and fact-checks textual claims.

Backend: Django + Celery. Frontend: React + Vite. Infra: Postgres, Redis, MinIO, self-hosted Ollama. Production at [prooflayer.cloud](https://prooflayer.cloud).

## Features

- **7 parallel analyzers** via Celery chord:
  - `metadata` - EXIF/XMP signatures, edit-software flags
  - `ela` - Error Level Analysis for splice/clone detection
  - `siglip_detector` - SigLIP-base binary AI/real classifier (Apache-2.0)
  - `community_forensics` - ViT-S/16 trained on 4803 generators (NeurIPS 2024, MIT)
  - `npr_detector` - NPR ViT deepfake corroborator
  - `llm_vision` - qwen2.5vl:3b on Ollama for scene reasoning
  - `audio_spectrogram` - librosa spectral features for synthetic-voice detection
  - `video_frames` - uniform-sampled frames through the image ensemble
- **Fact-check pipeline** (async Celery): spaCy NER claim extraction -> DuckDuckGo web context -> Ollama LLM assessment -> Google Fact Check API cross-reference
- **Provenance**: pHash/dHash/aHash against known-fake database, optional TinEye/Google Vision hooks
- **Browser extension** (MV3): Chrome + Firefox, one-click verify from any page
- Crowdsource voting (real / fake / uncertain) per submission
- Moderation review queue with verdict overrides
- SHA-256 result caching - same file returns instant cached verdict
- WeasyPrint PDF reports
- Embeddable JS widget for third-party sites
- Role-based access: Free / Pro / Education / Enterprise tiers via Stripe/Paddle
- JWT auth with httpOnly cookie refresh rotation

## Stack

**Backend:** Django 5.1, DRF 3.15, Celery 5.4, PostgreSQL 16, Redis 7, MinIO, Ollama, transformers + torch (CPU), spaCy, librosa, OpenCV, Pillow, imagehash, WeasyPrint, django-anymail[resend]

**Frontend:** React 18, Vite 6, TypeScript 5.6, Tailwind 3, Zustand 5, TanStack Query 5, React Router 7, Framer Motion, Axios

**Infra:** Docker Compose, self-hosted Ubuntu homelab, Caddy + Cloudflare Tunnel, Sentry, Flower

## Architecture

```
[ React SPA ]  <-->  [ Browser Extension (MV3) ]
(Vite + Nginx)
      |
      | HTTPS / JWT
      v
[ Django API ]  <------->  [ PostgreSQL ]
(gunicorn)                 [ MinIO (S3) ]
      |
      | Celery broker
      v
[ Redis ]  <-- Django cache (factcheck stage keys)
      |
      v
[ Celery Worker ]  (queues: default, ml, reports)
      |
      v
[ Ollama ]
  qwen2.5:3b + qwen2.5vl:3b
```

**Upload pipeline:**

1. Client uploads file. Django writes to MinIO, creates `Submission` row.
2. `process_submission` task queued. SHA-256 + perceptual hashes computed.
3. Cache hit: same SHA -> clone prior verdict and return instantly.
4. Otherwise: chord of analyzer tasks fans out on `ml` queue.
5. `aggregate_verdicts` chord callback computes weighted final score.
6. Provenance and factcheck tasks run on `default` queue.
7. Frontend WebSocket + polling renders live progress and final result.

**Factcheck pipeline (async):**

1. `POST /api/v1/factcheck/check/` -> dispatches `run_factcheck` Celery task, returns `{task_id}`.
2. Frontend polls `GET /api/v1/factcheck/status/{task_id}/` every 1.5s.
3. Task stages written to Redis cache (`fc:{task_id}`, TTL 600s): `extracting` -> `searching` -> `assessing` -> `cross_referencing` -> `done`.

## Local development

Requires Docker and Docker Compose.

```bash
git clone <repo>
cd prooflayer
docker-compose up --build
```

First boot pulls Ollama models (~5 GB). Wait for `ollama_init` to exit before submitting LLM-dependent uploads.

| Service     | URL                              | Notes                           |
|-------------|----------------------------------|---------------------------------|
| Frontend    | http://localhost:5173            | Vite dev server                 |
| Backend API | http://localhost:8000/api/v1     | Django + DRF                    |
| Swagger     | http://localhost:8000/api/docs/  | OpenAPI explorer                |
| Admin       | http://localhost:8000/admin/     | Requires superuser              |
| Flower      | http://localhost:5555            | Celery monitor                  |
| MinIO       | http://localhost:9001            | Console (minioadmin/minioadmin) |
| Ollama      | http://localhost:11434           | LLM API                         |

```bash
docker-compose exec backend python manage.py createsuperuser
```

## Environment variables

| Variable                  | Default                    | Purpose                        |
|---------------------------|----------------------------|--------------------------------|
| `SECRET_KEY`              | insecure-dev-key           | Django secret                  |
| `DATABASE_URL`            | (none)                     | Postgres DSN                   |
| `REDIS_URL`               | redis://redis:6379/0       | Broker + Django cache          |
| `CELERY_BROKER_URL`       | redis://redis:6379/0       | Celery broker                  |
| `OLLAMA_URL`              | http://ollama:11434        | Ollama endpoint                |
| `OLLAMA_MODEL`            | qwen2.5:3b                 | Text LLM                       |
| `OLLAMA_VISION_MODEL`     | qwen2.5vl:3b               | Vision LLM                     |
| `AWS_ACCESS_KEY_ID`       | (none)                     | MinIO/S3 key                   |
| `AWS_SECRET_ACCESS_KEY`   | (none)                     | MinIO/S3 secret                |
| `AWS_STORAGE_BUCKET_NAME` | prooflayer-media           | Bucket name                    |
| `AWS_S3_ENDPOINT_URL`     | http://minio:9000          | MinIO endpoint                 |
| `RESEND_API_KEY`          | (none)                     | Transactional email (Resend)   |
| `SENTRY_DSN`              | (none)                     | Optional error tracking        |
| `GOOGLE_FACT_CHECK_KEY`   | (none)                     | Optional fact-check API        |
| `TINEYE_API_KEY`          | (none)                     | Optional reverse image search  |

Frontend (`frontend/.env.local`):

```
VITE_API_URL=http://localhost:8000/api/v1
```

## Project layout

```
backend/
  analyzers/     # 7 analyzers, registry, Celery tasks, aggregator
  content/       # Submission model, upload pipeline, PDF reports, widget
  crowdsource/   # Voting model and endpoints
  reports/       # Moderation reports
  provenance/    # Perceptual hash matching, reverse search
  factcheck/     # Async fact-check: NER, web search, LLM, Google FC API
  users/         # Custom User, JWT auth, email verification
  config/        # Settings, Celery app, URLs
frontend/
  src/
    pages/       # Landing, Login, Upload, Dashboard, Result, FactCheck, Pricing, ...
    components/  # Layout, AnalyzerTimeline, VotingPanel, SubscriptionGate, ...
    hooks/       # TanStack Query hooks
    api/         # Axios client and endpoints
    stores/      # Zustand (auth, upload)
    types/       # Shared TS interfaces
  public/
    widget.js    # Embeddable badge script
extension/       # MV3 browser extension (Chrome + Firefox)
wiki/            # Internal knowledge base (Obsidian-compatible)
deploy/          # Production deployment scripts and Caddy config
```

## Production

See `deploy/README.md`. Self-hosted Ubuntu homelab behind Cloudflare Tunnel. Deploy:

```bash
~/deploy.sh prooflayer
```

## Tests

```bash
pytest backend/
pytest backend/factcheck/     # one app
pytest -k test_caching        # filter by keyword
```

## License

Copyright (c) 2026 Sole Proprietor ProofLayer. All rights reserved.

This software and its source code are proprietary. No part of this repository may be copied, modified, distributed, or used without explicit written permission from the owner.
