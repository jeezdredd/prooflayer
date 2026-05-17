---
type: service
created: 2026-05-14
---

# Redis

Dual role: Celery broker AND Celery result backend AND Django cache (if configured).

## Container

```yaml
redis:
  image: redis:7.4-alpine
  ports: ["6379:6379"]
```

## URLs

- `REDIS_URL=redis://redis:6379/0`
- `CELERY_BROKER_URL=redis://redis:6379/0`

Both Django and Celery hit DB 0.

## Used by

- Celery task queue (broker)
- Celery task results (backend)
- Chord synchronization (chord_join key)
- Possible: Django cache framework (LocMem fallback)
- [[api/system-status]] probe (`client.ping()`)

## See also

- [[services/celery-workers]]
- [[concepts/submission-pipeline]] - chord coordination
