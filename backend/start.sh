#!/bin/sh
set -e

python manage.py migrate --noinput

celery -A config.celery worker --loglevel=info --queues=default,ml,reports --concurrency=2 &

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 1 \
  --timeout 300 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
