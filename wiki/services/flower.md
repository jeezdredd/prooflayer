---
type: service
created: 2026-05-14
---

# Flower (Celery Monitor)

Web UI for celery workers + tasks. Port 5555.

## Container

```yaml
flower:
  build: backend/Dockerfile
  command: celery -A config.celery flower --port=5555
  ports: ["5555:5555"]
  environment:
    - REDIS_URL=redis://redis:6379/0
    - CELERY_BROKER_URL=redis://redis:6379/0
```

## URL

http://localhost:5555

## Tabs

- **Workers** - online list, pool processes, mem usage, runtime
- **Tasks** - history with name, UUID, state (SUCCESS/FAILURE/STARTED/PENDING), args, kwargs, result, received/started timestamps
- **Broker** - queue lengths per Q (default/ml/reports)
- **Documentation** - inline help

## In-app status

For high-level health visible to end users: [[api/system-status]] feeds `/status` page in the React app (workers count, active tasks, ollama loaded models). Flower stays as power-user tool.

## See also

- [[services/celery-workers]]
- [[api/system-status]]
