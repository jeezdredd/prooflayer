---
type: api
created: 2026-05-14
---

# REST API Endpoints

Base: `/api/v1/`. Auth: JWT bearer (`Authorization: Bearer <access>`). Schema: drf-spectacular at `/api/schema/`, Swagger UI at `/api/docs/`.

## Auth (`users.urls`)

```
POST /api/v1/auth/register/         { email, username, password, password_confirm } -> { access, refresh, user }
POST /api/v1/auth/login/            { email, password } -> { access, refresh, user }
POST /api/v1/auth/refresh/          { refresh } -> { access }
GET  /api/v1/auth/me/               -> user
GET  /api/v1/auth/health/           -> { status: "ok" }
```

## Content (`content.urls`)

```
GET    /api/v1/content/submissions/                      list (paginated, filterable)
POST   /api/v1/content/submissions/                      multipart upload -> Submission
GET    /api/v1/content/submissions/stats/                {total, by_verdict, by_status, avg_score, known_fake_hits}
GET    /api/v1/content/submissions/{id}/                 detail w/ analysis_results + similar
DELETE /api/v1/content/submissions/{id}/                 (if allowed)
POST   /api/v1/content/submissions/{id}/override/        staff VerdictOverride
GET    /api/v1/content/submissions/{id}/report.pdf       PDF export (reports app)
GET    /api/v1/content/submissions/{id}/status/          AllowAny, returns {id, status, final_verdict, final_score}
GET    /api/v1/content/widget/embed/{sha256}/            public widget JSON
POST   /api/v1/content/analyze-url/                      {url} -> {submission_id}, anonymous quota enforced
GET    /api/v1/content/feed/                             public feed
GET    /api/v1/content/feed/{id}/                        public submission detail
```

### analyze-url endpoint

`POST /api/v1/content/analyze-url/` - accepts `{url}` JSON body. Downloads image at URL (SSRF-guarded), creates Submission, dispatches analysis. Auth optional - anonymous requests tracked via `AnonymousQuota` (5/day per IP). Returns 201 `{submission_id}`. Returns 429 with `{error: "anonymous_limit_reached"}` when quota hit.

SSRF guard: resolves hostname -> rejects private/loopback/link-local IPs before fetch.

### submission status endpoint

`GET /api/v1/content/submissions/{id}/status/` - no auth required (`AllowAny`). Returns `{id, status, final_verdict, final_score}`. Used by browser extension to poll without JWT.

Filters: `?status=...&final_verdict=...&search=filename`. Pagination via `?page=N` (default page_size 25).

## Analyzers (`analyzers.urls`)

```
GET  /api/v1/analyzers/configs/                -> AnalyzerConfig list (admin tunable)
GET  /api/v1/analyzers/results/<submission_id>/ -> AnalysisResult list (owner-scoped)
POST /api/v1/analyzers/retrain/   { media_type, force?, epochs? }  -> { task_id }   (IsAdminUser)
GET  /api/v1/analyzers/retrain/runs/                                -> last 10 RetrainRun rows (IsAdminUser)
```

`retrain/` dispatches `run_weekly_retrain` to fine-tune [[analyzers/custom_detector]] from review-queue-approved samples (`force` lowers min-samples to 1 for testing; `epochs` 1-10). Emails the triggering user + Discord on finish. See [[services/celery-workers]].

## Crowdsource (`crowdsource.urls`)

```
POST /api/v1/crowdsource/votes/   { submission, vote }   real/fake/uncertain
GET  /api/v1/crowdsource/votes/?submission={id}
```

## Reports (`reports.urls`)

```
POST /api/v1/reports/generate/    { submission_id } -> async task id
GET  /api/v1/reports/{id}/        -> Report row (download_url when ready)
```

## Provenance (`provenance.urls`)

```
GET  /api/v1/provenance/{submission_id}/   -> external source matches
```

## Factcheck (`factcheck.urls`)

```
POST /api/v1/factcheck/check/         { text }                  -> { task_id }
GET  /api/v1/factcheck/status/{task_id}/                        -> { stage, progress, result?, error? }
POST /api/v1/factcheck/export/        { result, text }          -> application/pdf
POST /api/v1/factcheck/fetch-url/     { url }                   -> { text, title }
POST /api/v1/factcheck/extract-doc/   multipart: file=PDF|DOCX  -> { text }
```

Async Celery pipeline. Stages: `extracting` (10%) -> `searching` (30%) -> `assessing` (55%) -> `cross_referencing` (80%) -> `done` (100%). Stage payload cached in Redis (key `fc:{task_id}`, TTL 600s). Frontend polls every 1.5s until `stage == "done"` or `"error"`.

Pipeline: spaCy NER -> DuckDuckGo search + Wikipedia lookup -> Ollama LLM assessment (with confidence 0-100) -> Google Fact Check Tools per claim, top-3 web sources attached.

Claim shape:
```json
{
  "claim": "...",
  "assessment": "likely_true|likely_false|uncertain",
  "confidence": 0-100,
  "explanation": "...",
  "sources": [{"title", "url"}, ...],
  "wikipedia": {"title", "extract", "url"} | null,
  "fact_checks": [...]
}
```

`fetch-url/` enforces SSRF guard via `backend/common/url_safety.py:validate_public_url`, capped at 1 MB, HTML-only. `extract-doc/` capped at 10 MB.

See [[services/factcheck]] for full details.

## System

```
GET /api/v1/system/status/   -> see [[api/system-status]]
```

## OpenAPI

```
GET /api/schema/             OpenAPI 3 JSON
GET /api/docs/               Swagger UI
GET /api/redoc/              ReDoc
```

## See also

- [[services/backend]]
- [[api/system-status]]
- [[models/Submission]]
