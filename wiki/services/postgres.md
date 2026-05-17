---
type: service
created: 2026-05-14
---

# Postgres

Primary relational store. Postgres 16 alpine.

## Container

```yaml
db:
  image: postgres:16-alpine
  ports: ["5432:5432"]
  environment:
    POSTGRES_DB: prooflayer
    POSTGRES_USER: prooflayer
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-prooflayer_dev}
  volumes:
    - db_data:/var/lib/postgresql/data
```

Healthcheck: `pg_isready -U prooflayer`.

## Connection URL

`DATABASE_URL=postgres://prooflayer:prooflayer_dev@db:5432/prooflayer`

## Tables (Django auto-managed)

Key tables (see model pages for full schemas):
- `users_user` - [[models/User]]
- `submissions` - [[models/Submission]]
- `analysis_results` - [[models/AnalysisResult]]
- `analyzer_configs` - [[models/AnalyzerConfig]]
- `known_fake_hashes` - [[models/KnownFakeHash]]
- `crowdsource_*` - vote tables
- `auth_*`, `django_*` - framework tables

## Migrations

`python manage.py migrate` runs in backend entrypoint. Manual: `docker compose exec backend python manage.py migrate`.

## See also

- [[architecture]]
- [[services/backend]]
