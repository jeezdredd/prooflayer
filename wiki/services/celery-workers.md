---
type: service
created: 2026-05-14
---

# Celery Workers

Background analyzer pool. One worker process per container in dev.

## Command (current)

`docker-compose.yml` runs the worker as a shell chain - preload HF models on boot, then start celery:

```
python -u manage.py preload_models || true
exec python -u -m celery -A config.celery worker --loglevel=info -Q default,ml,reports --pool=solo -E
```

- `--pool=solo` - REQUIRED. The GPU/ROCm worker cannot use the default prefork pool: HIP/ROCm is fork-unsafe (same as CUDA), the first `model.to('cuda')` in a forked child hangs uninterruptibly. Solo runs the task in the MainProcess. See [[services/gpu-rocm]].
- `-E` - emit task events so [[services/flower]] sees activity.
- Under solo, `--concurrency`/`--max-tasks-per-child`/`--max-memory-per-child` are no-ops, so they were dropped. The in-process `_state` model cache then persists for the worker lifetime (load once, reuse).
- `preload_models` (`backend/analyzers/management/commands/preload_models.py`) pre-pulls siglip / community_forensics / npr / clip ensemble so the first user submission isn't the one that downloads ~GBs. HF cache is persisted via the `hf_cache` volume.

## Env

The worker uses `env_file: .env` so every secret in `.env` is injected literally (no `${}` interpolation issues for keys with special chars). On the homelab it must include:

```
DJANGO_SETTINGS_MODULE=config.settings.prod   # prod = S3/MinIO storage + requires SECRET_KEY
SECRET_KEY=...
DATABASE_URL=postgres://prooflayer:<pw>@db:5432/prooflayer
REDIS_URL / CELERY_BROKER_URL=redis://redis:6379/0
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_VISION_MODEL=qwen2.5vl:3b
HF_TOKEN= / HF_HOME=/root/.cache/huggingface
AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_STORAGE_BUCKET_NAME / AWS_S3_ENDPOINT_URL / AWS_S3_CUSTOM_DOMAIN
GOOGLE_FACT_CHECK_KEY=
HSA_OVERRIDE_GFX_VERSION= / HIP_VISIBLE_DEVICES=0   # ROCm GPU
PYTORCH_NO_CUDA_MEMORY_CACHING=1 / OMP_NUM_THREADS=2
```

> [!warning] env-drift
> The ROCm worker is rebuilt MANUALLY (`WORKER_DOCKERFILE=backend/Dockerfile.rocm docker compose up celery_worker`), NOT via deploy.sh, so it only sees `docker-compose.yml` + `.env`. Any secret the backend needs, the worker needs too - keep them all in `.env`. Past drifts: missing POSTGRES_PASSWORD (DB auth fail -> submissions stuck pending), missing AWS creds (local storage fallback -> FileNotFoundError), wrong DJANGO_SETTINGS_MODULE (dev -> local storage). See [[services/gpu-rocm]].

## Queues

- `default` - orchestration (`process_submission`, `dispatch_analysis`, `aggregate_verdicts`, factcheck) + light analyzers (metadata, ela)
- `ml` - heavy detectors (siglip_detector, community_forensics, npr_detector, custom_detector, llm_vision, llm_text, video_frame, audio_spectrogram)
- `reports` - PDF generation

Worker subscribes to all three with `-Q default,ml,reports`.

## Tasks

`backend/analyzers/tasks.py`:

- `dispatch_analysis(submission_id)` - fans out per-analyzer
- `run_analyzer(submission_id, config_id)` - single analyzer execution
- `aggregate_verdicts(results, submission_id)` - chord callback

`backend/content/tasks.py`:

- `process_submission(submission_id)` - kicks off pipeline

`backend/provenance/tasks.py`:

- `run_provenance_check(submission_id)` - external source matching

`backend/factcheck/tasks.py`:

- `run_factcheck(text)` - async factcheck pipeline: spaCy NER -> DuckDuckGo search + Wikipedia lookup -> Ollama LLM assess (with confidence) -> Google Fact Check. Writes stage progress to Redis cache (`fc:{task_id}`). Goes to `default` queue.

`backend/analyzers/tasks.py` (retrain):

- `run_weekly_retrain(media_type, triggered_by_id, min_samples_override, epochs_override)` - fine-tunes the custom_detector from review-queue-approved submissions; emails the triggering user + Discord on finish. Triggered by `POST /api/v1/analyzers/retrain/` (admin). See [[api/endpoints]].

## Status messages

`ANALYZER_STATUS_MESSAGES` dict maps analyzer name -> user-facing string. Set on `submission.status_message` per-task so UI shows live "Analyzing image with vision AI...".

## Monitoring

See [[services/flower]].

## See also

- [[concepts/submission-pipeline]]
- [[fixes/oom-sigkill]]
- [[infrastructure/celery-tuning]]
