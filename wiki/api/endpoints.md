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
GET    /api/v1/content/widget/embed/{sha256}/            public widget JSON
```

Filters: `?status=...&final_verdict=...&search=filename`. Pagination via `?page=N` (default page_size 25).

## Analyzers (`analyzers.urls`)

```
GET /api/v1/analyzers/configs/   -> AnalyzerConfig list (admin tunable)
GET /api/v1/analyzers/results/   -> AnalysisResult flat list
```

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
POST /api/v1/factcheck/run/   { text }   -> { claims: [...], overall_verdict }
```

Pipeline: spaCy NER -> Ollama LLM extraction -> Google Fact Check Tools lookup per claim.

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
