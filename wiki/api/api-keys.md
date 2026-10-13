---
type: api
created: 2026-10-13
source: backend/users/{models,authentication,api_keys,webhooks,tasks}.py, frontend/src/pages/DevelopersPage.tsx
---

# API keys and webhooks

Promised on the Pro tier ("API access") since launch, built 2026-10-13. Gated by
`billing.permissions.CanUseApi` (`can_api`: Pro, Education, Enterprise, staff).

## Keys

- `users.ApiKey`: `pl_` + 43 url-safe chars. Only `prefix` (first 11 chars) and the sha256
  `key_hash` are stored; the raw key is returned once from `POST /api/v1/auth/api-keys/`.
- Auth: `Authorization: Api-Key pl_...` or `X-API-Key: pl_...`
  (`users.authentication.ApiKeyAuthentication`, after JWT in `DEFAULT_AUTHENTICATION_CLASSES`).
  `request.auth` is the `ApiKey`. Rejected with 401 when revoked, unknown, the account is
  disabled, or the user's plan no longer grants `can_api` (a downgrade turns keys off without
  revoking them).
- `last_used_at` written at most once a minute per key.
- Throttle scope `api` = 120/min per key (`common.throttling.ApiKeyRateThrottle`, no-op for
  browser sessions). Uploads additionally follow the `upload` scope and the monthly quota.
- Management endpoints (`GET/POST /auth/api-keys/`, `PATCH/DELETE /auth/api-keys/<id>/`) refuse
  requests authenticated *by* an API key: a leaked key cannot mint or revoke keys. DELETE
  revokes (sets `revoked_at`), it does not delete. Max 10 active keys.

## Webhooks

- Optional `webhook_url` per key, https only, must resolve to a public address
  (`common.url_safety.validate_public_url`). A `whsec_...` secret is issued with it.
- `Submission.api_key` records which key uploaded the file. `aggregate_verdicts` enqueues
  `users.tasks.deliver_submission_webhook` for those submissions.
- Delivery: `safe_post` (re-validates, pins the resolved IPs, never follows redirects), 10 s
  timeout, retried with backoff (30 s .. 10 min, 3 tries) on network errors and 5xx. Blocked URLs
  are recorded and not retried. `last_webhook_at` / `last_webhook_status` on the key.
- Body: canonical JSON (`sort_keys`, no spaces) with `event`, `submission_id`, `status`,
  `verdict`, `score`, `tribunal_version`, `tribunal_fingerprint`, `original_filename`,
  `completed_at`.
- Headers: `X-ProofLayer-Event`, `X-ProofLayer-Timestamp`,
  `X-ProofLayer-Signature: sha256=HMAC_SHA256(secret, "<timestamp>.<raw body>")`.

## Frontend

`/developers` (sidebar "API"): create, one-time reveal of key and secret, revoke, last use and
last webhook status per key, curl examples and a Python signature check.

## See also

- [[api/endpoints]], [[concepts/tribunal]] (stamp in the webhook body)
