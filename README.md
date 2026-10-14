# ProofLayer

Multi-modal content verification platform. Detects deepfakes, AI-generated images, manipulated media, tracks provenance, and fact-checks textual claims.

Backend: Django + Celery. Frontend: React + Vite. Infra: Postgres, Redis, MinIO, self-hosted Ollama. Production at [prooflayer.cloud](https://prooflayer.cloud).

## Features

### Tribunal: the detector ensemble

Analyzers are seeded as DB configs (`analyzers/management/commands/seed_analyzers.py`), fanned out
via a Celery chord and combined by `analyzers/aggregator.py` into one verdict. Every verdict is
stamped with the Tribunal version and a fingerprint of the roster (`analyzers/ensemble.py`); the
changelog with measured numbers lives in `wiki/concepts/tribunal.md`.

**Images and video**
- `community_forensics` (3.5) - Community Forensics ViT-S/16 (NeurIPS 2024), calibrated score
- `custom_detector` (3.5) - ViT retrained on the review queue and current generators, own calibration
- `clip_probe` (2.5) - linear probe on CLIP embeddings, an independent backbone
- `ai_detector` (1.0) - two image classifiers behind a photographic-content gate
- `metadata` (1.5) - EXIF/XMP, PNG generation parameters, C2PA Content Credentials
- `ela` (0.75) - Error Level Analysis, manipulation channel only, never votes on AI
- `llm_vision` (1.5) - Ollama vision model that must name a concrete defect
- `video_frame` (2.0) - frames across the whole clip through the image bench, median verdict

**Audio**
- `audio_spectrogram` (2.0) - spectral features for synthetic-voice artifacts

**Text (en / ru / fr; PDF and DOCX supported)**
- `text_classifier` (2.5) - multilingual-e5-small fine-tuned on human essays, pre-2022 Wikipedia,
  fresh generations from current open models and humanizer-style rewrites; per-language calibration,
  logit-margin score, per-passage scores. Alone it can only flag, never convict.
- `text_evasion` (2.0) - homoglyphs, invisible characters, odd spaces, hidden/white/tiny DOCX text
- Context members (never vote; a flag sends the work to human review):
  - `text_grade_fit` - vocabulary and readability against the class year, then against the student's
    own usual level: a strong student who always writes above the class is not flagged
  - `text_style` - drift from the same student's earlier class work
  - Personal comparisons (age fit, style, class radar jumps) say "not enough data" until the student
    has 3 earlier works; the class radar compares works only from 5 works by 4 students
  - `text_citations` - invented DOIs, arXiv ids, ISBNs, links, references and quotes, checked
    against doi.org, arXiv, Open Library, Google Books, OpenAlex and Crossref; reference-list format
    for APA, MLA, Chicago, Harvard, IEEE, Vancouver, GOST and ISO 690
  - `text_genre` - argument essay, narrative, retelling, analysis, description, report, letter, poem
  - `text_shadow` - closeness to AI answers the teacher generated for the assignment

### Education (Classroom)
- Schools and classes with join codes, class year, teacher and admin roles; class uploads bill the school
- Originality check on every text upload: winnowed fingerprints, e5 sentence vectors for rewording and
  translation (ru/en/fr), web search through self-hosted SearXNG
- Class radar: works by different students built on one skeleton, and sudden jumps in a student's level
- Assignment shadow: the server answers the assignment with AI as students of several ages would
- Teacher report per work with every signal and its evidence; verdict objections with deadlines

### Platform
- Fact-check pipeline (async Celery): spaCy claim extraction, web and Wikipedia context, Ollama
  assessment, Google Fact Check cross-reference; text, URL (SSRF-guarded) or PDF/DOCX input
- Provenance: perceptual hashes against known fakes and earlier copies
- Compare two files judge by judge; human review queue whose corrections retrain `custom_detector`
- API keys with signed completion webhooks, batch upload (files or ZIP) with CSV export
- PDF reports, embeddable widget, MV3 browser extension (Chrome + Firefox)
- Free / Pro / Education / Enterprise tiers, JWT auth with httpOnly refresh rotation
- Torch detectors run on GPU when available (AMD ROCm worker, see `wiki/services/gpu-rocm.md`)

## Stack

**Backend:** Django 5.1, DRF 3.15, Celery 5.4, PostgreSQL 16 (pgvector), Redis 7, MinIO, Ollama, transformers + torch (CPU, or ROCm on the GPU worker), spaCy, librosa, OpenCV, Pillow, imagehash, WeasyPrint, trafilatura + pypdf + python-docx (factcheck doc/URL ingest), django-anymail[resend]

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
| `OLLAMA_MODEL`            | qwen2.5:3b                 | Fact-check and assignment shadow |
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
  analyzers/     # Tribunal members, text package (classifier, citations, genre, style...), aggregator
  classroom/     # Schools, classes, roster, class radar, assignment shadow
  plagiarism/    # Originality: fingerprints, sentence vectors, web search
  content/       # Submission model, upload pipeline, batches, PDF reports, widget
  billing/       # Plans, quotas, tier gates
  api/           # API keys, webhooks, system status, roadmap
  crowdsource/   # Voting
  reports/       # Moderation reports
  provenance/    # Perceptual hash matching
  factcheck/     # Async fact-check
  users/         # Custom User, JWT auth, email verification
  common/        # URL safety, document extraction, throttling
  config/        # Settings, Celery app, URLs
frontend/
  src/
    pages/       # Landing, Upload, Result, Classroom, Developers, FactCheck, Pricing, ...
    components/  # AnalyzerTimeline, TextReport, OriginalityPanel, landing/*, ...
    api/         # Axios client and endpoints
    stores/      # Zustand
    types/       # Shared TS interfaces
scripts/         # Dataset builders (MLX generation, Wikipedia fetch)
extension/       # MV3 browser extension (Chrome + Firefox)
wiki/            # Internal knowledge base (Obsidian-compatible)
deploy/          # Production compose, deploy scripts, Caddy config
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
