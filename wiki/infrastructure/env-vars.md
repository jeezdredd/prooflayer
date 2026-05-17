---
type: infrastructure
created: 2026-05-14
---

# Env Vars

`.env` (gitignored). `.env.example` shows full list.

## Django / Backend

| Var | Default | Purpose |
|-----|---------|---------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | settings split |
| `SECRET_KEY` | `change-me-in-production` | Django session/CSRF |
| `DATABASE_URL` | `postgres://...` | DB connection |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | csv |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | csv |

## Postgres

| Var | Default | Purpose |
|-----|---------|---------|
| `POSTGRES_DB` | `prooflayer` | |
| `POSTGRES_USER` | `prooflayer` | |
| `POSTGRES_PASSWORD` | `prooflayer_dev` | |
| `POSTGRES_HOST` | `db` | service name |
| `POSTGRES_PORT` | `5432` | |

## Redis / Celery

| Var | Default | Purpose |
|-----|---------|---------|
| `REDIS_URL` | `redis://redis:6379/0` | client |
| `CELERY_BROKER_URL` | same | broker |

## Ollama

| Var | Default | Purpose |
|-----|---------|---------|
| `OLLAMA_URL` | `http://ollama:11434` | endpoint |
| `OLLAMA_MODEL` | `qwen2.5:3b` | text LLM (analyzer + factcheck) |
| `OLLAMA_VISION_MODEL` | `qwen2.5vl:3b` | vision LLM |
| `OLLAMA_MAX_LOADED_MODELS` | `1` | swap-only mode |
| `OLLAMA_KEEP_ALIVE` | `2m` | idle unload timeout |

## HF / ML

| Var | Default | Purpose |
|-----|---------|---------|
| `HF_TOKEN` | (empty) | private model auth |
| `OMP_NUM_THREADS` | `2` | PyTorch CPU thread cap |
| `PYTORCH_NO_CUDA_MEMORY_CACHING` | `1` | no GPU here |

## Frontend (Vite)

| Var | Default | Purpose |
|-----|---------|---------|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | API base |

Note: Vite env vars must be prefixed `VITE_` to be exposed to client bundle.

## MinIO / S3

| Var | Default | Purpose |
|-----|---------|---------|
| `MINIO_ROOT_USER` | `minioadmin` | |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | |
| `AWS_STORAGE_BUCKET_NAME` | `prooflayer-media` | bucket name |
| `AWS_S3_ENDPOINT_URL` | (varies) | s3-compat endpoint |

## Other

| Var | Purpose |
|-----|---------|
| `SENTRY_DSN` | error tracking, optional |

## Reading at runtime

```python
# Django settings
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "llava:7b")
```

Frontend:
```ts
const API_URL = import.meta.env.VITE_API_URL || "/api/v1";
```

## See also

- [[infrastructure/docker-compose]]
- [[services/ollama]]
