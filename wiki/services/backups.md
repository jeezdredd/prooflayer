---
type: service
created: 2026-05-28
source: backend/api/tasks.py
---

# Postgres Backups

Nightly `pg_dump` -> gzip -> MinIO bucket `prooflayer-backups/daily/`. Retention 14 days, swept after each successful upload.

## Schedule

Celery beat embedded in `celery_worker` (`--beat --schedule=/tmp/celerybeat-schedule`). Trigger: cron `15 3 * * *` (03:15 UTC daily).

Defined in `backend/config/celery.py`:
```python
app.conf.beat_schedule = {
    "nightly-postgres-backup": {
        "task": "api.tasks.backup_postgres",
        "schedule": crontab(hour=3, minute=15),
    },
}
```

## Task flow

`api.tasks.backup_postgres`:
1. Parse `DATABASE_URL` env.
2. `pg_dump --no-owner --no-acl --format=plain` via subprocess. `PGPASSWORD` from URL.
3. Gzip in-memory.
4. `boto3.put_object` -> `s3://prooflayer-backups/daily/prooflayer-{YYYYMMDDTHHMMSSZ}.sql.gz`.
5. Sweep: list bucket, delete objects with `LastModified < now - 14d`.

## Manual run

```bash
ssh seb0107@ubuntu-dev "cd /srv/prooflayer/current/deploy && \
  docker compose -f compose.prod.yml exec -T celery_worker \
  celery -A config.celery call api.tasks.backup_postgres"
```

## Restore

Pull latest backup:
```bash
mc cp local/prooflayer-backups/daily/prooflayer-XXX.sql.gz ./restore.sql.gz
gunzip restore.sql.gz
docker compose -f compose.prod.yml exec -T db psql -U prooflayer -d prooflayer < restore.sql
```

## Why MinIO, not host volume

- Single source of truth (same storage as media)
- Survives container/host wipe
- Easy off-site rsync from MinIO later

## Constraints

- `postgresql-client` package added to backend image (commit *) so `pg_dump` exists in worker.
- Beat enabled on the single worker only (no separate beat container) -> if we scale workers, must isolate beat to one or use `RedBeat`.
- Bucket auto-created on first run via `_ensure_bucket`.

## See also

- [[services/celery-workers]]
- [[services/minio]]
- [[services/postgres]]
