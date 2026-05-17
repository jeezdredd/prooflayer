---
type: architecture
created: 2026-05-14
---

# Architecture

```
┌──────────┐  HTTP   ┌──────────┐
│ Frontend │────────>│  Backend │ ──── Postgres
│ Vite 5173│  /api   │ Django   │ ──── Redis (broker + cache)
└──────────┘         │ 8000     │ ──── MinIO (S3)
                     └──────────┘
                          │ celery
                          ▼
                  ┌────────────────┐
                  │ celery_worker  │ ── Ollama (LLM)
                  │ Q: default/ml/ │ ── HF transformers (in-proc)
                  │    reports     │
                  └────────────────┘
                          │
                          ▼ flower :5555
```

## Services (docker-compose)

| Service | Role | Port | Image |
|---------|------|------|-------|
| `backend` | Django + DRF API | 8000 | local Dockerfile |
| `celery_worker` | Async task runner | - | local Dockerfile |
| `flower` | Celery monitor UI | 5555 | local Dockerfile |
| `db` | Postgres 16 | 5432 | `postgres:16-alpine` |
| `redis` | Broker + cache | 6379 | `redis:7.4-alpine` |
| `minio` | S3-compat blob store | 9000/9001 | `minio/minio:latest` |
| `minio_init` | Bucket bootstrap | - | `minio/mc:latest` |
| `ollama` | LLM inference | 11434 | `ollama/ollama` |
| `ollama_init` | `ollama pull qwen2.5:3b && pull qwen2.5vl:3b` | - | `ollama/ollama` |
| `frontend` | Vite dev server | 5173 | local Dockerfile |

See [[infrastructure/docker-compose]].

## Request flow (submission)

User uploads file -> see [[concepts/submission-pipeline]] for step-by-step.

## Code layout

```
backend/
  config/         settings, urls, celery app
  content/        Submission model, upload views, tasks
  analyzers/      pipeline, AnalyzerConfig, implementations/
  users/          custom User model
  crowdsource/    community votes
  reports/        PDF / JSON reports
  provenance/     external source lookups
  factcheck/      claim extraction + Google FC
  api/            cross-cutting views (system_views.py for /status)
  templates/      report HTML

frontend/src/
  pages/          one per route
  components/     UploadForm, AnalyzerTimeline, ResultCard, Layout, ...
  components/ui/  Toast, ShaderBackground, Skeleton, Spinner
  stores/         zustand: authStore, uploadStore, shaderStore
  hooks/          useAuth, useUpload, useDashboard
  api/            axios client, endpoints
  types/          TS interfaces
```

## Django apps (INSTALLED_APPS)

- `users` (custom AUTH_USER_MODEL)
- `content` (Submission, tasks, services)
- `analyzers` (AnalyzerConfig, AnalysisResult, dispatch tasks)
- `crowdsource` (votes)
- `reports` (PDF generation)
- `provenance` (external matching)
- `factcheck` (NER + Google FC Tools)
- `api` (system_views)

## Queues

Celery declares: `default`, `ml`, `reports`. AnalyzerConfig.queue field picks lane per analyzer. Worker subscribes to all three: `-Q default,ml,reports`.

See [[services/celery-workers]].
