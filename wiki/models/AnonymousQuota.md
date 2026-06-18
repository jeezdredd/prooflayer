---
type: model
created: 2026-06-17
source: backend/content/models.py
---

# AnonymousQuota

Per-IP daily rate limit for anonymous `analyze-url` submissions.

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `ip` | CharField(45) | IPv4 or IPv6 |
| `date` | DateField | auto today |
| `count` | PositiveIntegerField | default 0 |

`unique_together = [("ip", "date")]`

## Enforcement

`AnalyzeUrlView.post` (`backend/content/views.py`):
1. `select_for_update()` on `AnonymousQuota` for current IP + today.
2. If `count >= ANONYMOUS_DAILY_LIMIT` (5) -> return 429 `{error: "anonymous_limit_reached"}`.
3. Else increment count, save, proceed.
4. `IntegrityError` on race: retry with `get_or_create`.

## Limit

`ANONYMOUS_DAILY_LIMIT = 5` (constant in views.py). Resets at midnight UTC (new `date` row).

## See also

- [[api/endpoints]] - analyze-url endpoint
- [[services/extension]] - browser extension uses this quota
