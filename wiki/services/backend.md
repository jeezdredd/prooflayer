---
type: service
created: 2026-05-14
---

# Backend (Django)

Django 5.1 + DRF + drf-spectacular. Runs on port 8000.

## Entry point

`backend/manage.py`, `backend/config/wsgi.py` / `asgi.py`. Dev server: `python manage.py runserver 0.0.0.0:8000`.

Dockerfile builds image with Python 3.12, copies `backend/` into `/app`, runs migrations + collectstatic in entrypoint script.

## Settings

`config/settings/`:

- `base.py` - common
- `dev.py` - DEBUG=True, sqlite-or-postgres
- `prod.py` - DEBUG=False, security headers
- `test.py` - test runner settings

Loaded via `DJANGO_SETTINGS_MODULE=config.settings.dev` env var.

## INSTALLED_APPS

Custom apps:
- `users` ([[models/User]])
- `content` ([[models/Submission]])
- `analyzers` ([[models/AnalyzerConfig]] + [[models/AnalysisResult]])
- `crowdsource`
- `reports`
- `provenance`
- `factcheck`
- `api`

Third-party: `rest_framework`, `rest_framework_simplejwt`, `django_filters`, `corsheaders`, `drf_spectacular`, `storages`, `celery`, `debug_toolbar` (dev only).

## URL routing

`config/urls.py`:

```
/admin/                        Django admin
/api/v1/auth/                  users.urls (JWT)
/api/v1/content/               content.urls (submissions)
/api/v1/analyzers/             analyzers.urls (configs)
/api/v1/crowdsource/           crowdsource.urls (votes)
/api/v1/reports/               reports.urls (PDF)
/api/v1/provenance/            provenance.urls
/api/v1/factcheck/             factcheck.urls
/api/v1/auth/health/           liveness
/api/v1/system/status/         system_views.SystemStatusView - [[api/system-status]]
/api/schema/                   OpenAPI schema
/api/docs/                     Swagger UI
/api/redoc/                    ReDoc UI
```

## Celery app

`config/celery.py` defines `app = Celery("prooflayer")`. Loaded into Django at startup via `config/__init__.py` (else tasks publish to wrong queue - persistent memory item).

## Storage

- Dev: `MEDIA_ROOT` filesystem (with optional MinIO)
- Prod: `django-storages` to S3 (or MinIO)
- `storage_utils.local_file()` context manager pulls from remote to tmpfs for analyzer work

## See also

- [[architecture]]
- [[services/celery-workers]]
- [[api/endpoints]]
- [[infrastructure/env-vars]]
