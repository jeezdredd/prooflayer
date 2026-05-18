---
type: service
created: 2026-05-18
source: backend/api/system_views.py, backend/api/tasks.py, frontend/src/hooks/useVisitTracking.ts
---

# Visit Tracking (Discord notify)

Ops-side analytics. Once per browser session, frontend pings backend with current path. Backend resolves IP -> country/city via ip-api.com, posts Discord embed to channel.

## Privacy posture

- IP + geo are processed for analytics only. **Not stored** in DB. Only ephemeral Redis dedupe key (sha256(ip)[:16], TTL 1h).
- Disclosed in [[ConsentBanner]] (no opt-out yet - legitimate-interest under GDPR for site-owner analytics).
- No third-party JS tag fires. ip-api.com lookup runs server-side, browser never contacts it.
- Refusal to honour the cookie banner does not block service - tracking still runs because it does not store identifiers on the client.

## Flow

```
SPA mount -> useVisitTracking effect ->
  sessionStorage flag absent? ->
    POST /api/v1/system/visit/ { path, referrer }
backend RecordVisitView ->
  client IP from X-Forwarded-For (Caddy)
  Redis SET NX visit:{ip_hash}:{path} EX 3600  (dedupe)
  notify_visit.delay(ip, path, referrer, ua)
celery worker ->
  GET http://ip-api.com/json/{ip} (4s timeout, 45/min free quota)
  POST {DISCORD_WEBHOOK_URL} embed {ip, location, isp, path, referrer, ua}
```

## Endpoint

`POST /api/v1/system/visit/` - AllowAny, throttled to 30/min anon.

Request:
```json
{ "path": "/upload", "referrer": "https://twitter.com/..." }
```

Responses:
- `202` queued
- `204` deduped within 1h OR tracking disabled (no webhook env)
- `429` throttled

## Config

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/<id>/<token>
```

Empty -> feature off entirely (endpoint returns 204).

Webhook is wired to both `backend` and `celery_worker` services in `compose.prod.yml`. The actual HTTP POST to Discord fires from celery worker, so worker also needs the env.

## Dedupe + spam control

Same IP visiting same path within 1h -> dropped at API layer (Redis NX/EX 3600). Different paths from same IP -> separate notifications (so navigation pattern visible).

If Redis is unreachable, dedupe silently no-ops -> Discord may get bursts. Acceptable since Discord webhook itself rate-limits to 30/min per webhook.

## UA / proxy detection

ip-api.com returns `proxy: true` for known VPN/proxy IPs and `hosting: true` for hosting providers (DigitalOcean, AWS, etc.) - shown as `proxy` / `hosting/vpn` tags in the embed so we can tell bots from real visitors.

## See also

- [[services/auth-email]] - ConsentBanner copy
- [[infrastructure/env-vars]]
