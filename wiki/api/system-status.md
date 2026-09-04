---
type: api
created: 2026-05-14
updated: 2026-09-04
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
    "storage":  { "status": "skip", "reason": "no s3 endpoint configured" },
    "email":    { "status": "ok", "backend": "resend", "from_email": "...", "recent_failures": 0 },
    "analyzers": { "status": "ok", "active": 9, "expected": 9,
                   "ensemble": "Tribunal 1.0", "fingerprint": "3f9c1a7b2e04",
                   "drift": { "missing": [], "inactive_expected": [], "stale_active": [],
                              "class_mismatch": [], "weight_mismatch": [] } }
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
- `email`: configured backend + `EmailLog` rows with status `failed`/`console` in the last 24h
- `analyzers`: `analyzers.roster.roster_drift()` - diffs `AnalyzerConfig` rows against
  `seed_analyzers.ANALYZERS`. `down` (and `overall: degraded`) whenever any drift bucket is
  non-empty, with `error` naming the buckets and telling you to run `seed_analyzers`. Same logic
  backs the `analyzers.W001` system check and `manage.py seed_analyzers --check`. Added
  2026-09-04 after a weight rebalance sat unapplied on a worker-only rebuild; see
  [[analyzers/_index]].
  `ensemble` / `fingerprint` name the [[concepts/tribunal]] version and roster hash the
  backend is running, so a stale worker is visible even when the DB rows are in sync.

## Failure mode

Any probe raises -> status `"down"`, error truncated to 120 chars in response.

`overall` is `"degraded"` if any service NOT in `("ok", "skip")`.

## Frontend display

`/status` page renders 8 service rows (api, database, redis, celery, ollama, storage, email, analyzers) with:
- Pulse-dot status indicator (sage green / blood red / gray)
- Service label + lucide icon (Activity / Database / Zap / Cpu / Brain / HardDrive)
- One-line metrics (latency_ms, worker count, model list, `active/expected` for the roster)
- Description text
- Last-fetched timestamp

## See also

- [[services/flower]] - deeper celery debug
- [[frontend/routes]] - /status route
