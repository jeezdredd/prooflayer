---
type: api
created: 2026-05-14
source: backend/api/system_views.py
---

# GET /api/v1/system/status/

Public liveness probe across all infrastructure components. No auth required. Polled by [[frontend/routes|/status]] page every 5 seconds.

## Response shape

```json
{
  "overall": "operational" | "degraded",
  "checked_at": 1778396819.59,
  "services": {
    "api":      { "status": "ok" },
    "database": { "status": "ok", "latency_ms": 10.2 },
    "redis":    { "status": "ok", "latency_ms": 3.4, "version": "7.4.8" },
    "celery":   { "status": "ok", "workers": 1, "worker_names": ["celery@..."], "active_tasks": 0, "scheduled_tasks": 0 },
    "ollama":   { "status": "ok", "latency_ms": 12.5, "available_models": [...], "loaded_models": [] },
    "storage":  { "status": "skip", "reason": "no s3 endpoint configured" }
  }
}
```

## Probes

- `api`: hardcoded ok (we are responding)
- `database`: `SELECT 1` round-trip, measure latency
- `redis`: `client.ping()` + `INFO server` for version
- `celery`: `celery.control.inspect(timeout=2.0)`:
  - `stats()` -> worker names
  - `active()` -> running task count
  - `scheduled()` -> pending count
- `ollama`: `GET /api/tags` (available models) + `GET /api/ps` (currently loaded)
- `storage`: `GET {AWS_S3_ENDPOINT_URL}/minio/health/live` if configured

## Failure mode

Any probe raises -> status `"down"`, error truncated to 120 chars in response.

`overall` is `"degraded"` if any service NOT in `("ok", "skip")`.

## Frontend display

`/status` page renders 6 service rows with:
- Pulse-dot status indicator (sage green / blood red / gray)
- Service label + lucide icon (Activity / Database / Zap / Cpu / Brain / HardDrive)
- One-line metrics (latency_ms, worker count, model list)
- Description text
- Last-fetched timestamp

## See also

- [[services/flower]] - deeper celery debug
- [[frontend/routes]] - /status route
