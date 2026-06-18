---
type: fix
date: 2026-06-18
---

# Fix: Factcheck stage progress never updated (LocMemCache)

## Symptom

Factcheck pipeline stuck at 0% / "pending" forever after making it async with Celery. POST returned task_id, GET /status/ always returned `{"stage": "pending", "progress": 0}`.

## Root cause

Django default cache backend is `LocMemCache` - in-process memory only. The Celery worker called `cache.set(f"fc:{task_id}", payload)` into **its own process memory**. The Django backend called `cache.get(f"fc:{task_id}")` from **a different process** - always returned `None`.

## Fix

Added `CACHES` to `backend/config/settings/base.py`:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
```

Both processes now share Redis DB 0. `cache.set` in worker and `cache.get` in backend see same data.

## Key lesson

Any time Celery tasks write to Django cache and another Django process reads it, `LocMemCache` silently breaks. Must use Redis (or Memcached) cache backend for cross-process cache sharing.

## See also

- [[services/redis]]
- [[api/endpoints]] (factcheck status endpoint)
