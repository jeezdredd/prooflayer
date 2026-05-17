---
type: infrastructure
created: 2026-05-14
source: docker-compose.yml
---

# docker-compose Topology

9 services. Single shared bridge network.

## Services list

| Service | Image | Depends on | Ports | Volumes |
|---------|-------|-----------|-------|---------|
| `db` | postgres:16-alpine | - | 5432 | db_data |
| `redis` | redis:7.4-alpine | - | 6379 | - |
| `minio` | minio/minio:latest | - | 9000/9001 | minio_data |
| `minio_init` | minio/mc:latest | minio (healthy) | - | - |
| `ollama` | ollama/ollama | - | 11434 | ollama_data |
| `ollama_init` | ollama/ollama | ollama (healthy) | - | ollama_data |
| `backend` | local build | db, redis | 8000 | ./backend, media_data |
| `celery_worker` | local build | db, redis | - | ./backend, media_data |
| `flower` | local build | redis | 5555 | ./backend |
| `frontend` | local build | - | 5173 | ./frontend, anon node_modules |

## Healthchecks

- `db`: `pg_isready -U prooflayer` 10s
- `redis`: `redis-cli ping` 10s
- `minio`: `curl http://localhost:9000/minio/health/live` 10s
- `ollama`: `ollama list` 15s, start_period 30s

## Init containers

`minio_init` (`restart: "no"`):
```
mc alias set local http://minio:9000 USER PASS
mc mb -p local/${AWS_STORAGE_BUCKET_NAME}
mc anonymous set download local/${BUCKET}
```

`ollama_init` (`restart: "no"`):
```
ollama pull qwen2.5:3b && ollama pull qwen2.5vl:3b
```

## Volumes

- `db_data` - Postgres data dir
- `redis_data` - if persistence enabled (currently no AOF)
- `minio_data` - object store
- `ollama_data` - model weights cache (~5GB+)
- `media_data` - Django MEDIA_ROOT fallback
- `frontend` anon node_modules volume - preserves container pnpm install vs host

## Bind mounts

- `./backend:/app` (backend, celery_worker, flower) - live code reload
- `./frontend:/app` (frontend) - HMR works on host file edits

## Networking

All services share default compose network. Service names resolve as hostnames (e.g. `redis://redis:6379/0`, `http://ollama:11434`).

## Bringing up

```
docker compose up -d
```

Backend init script runs migrations + collectstatic. Frontend `pnpm dev --host 0.0.0.0` exposes on 5173. Ollama init blocks until models pulled. Backend healthy when DB is ready.

## See also

- [[architecture]]
- [[infrastructure/env-vars]]
- [[services/celery-workers]]
