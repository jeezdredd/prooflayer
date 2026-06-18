---
type: service
created: 2026-05-14
---

# Celery Workers

Background analyzer pool. One worker process per container in dev.

## Command

```
celery -A config.celery worker
  --loglevel=info
  -Q default,ml,reports
  --concurrency=1
  --max-tasks-per-child=4
  --max-memory-per-child=2500000
```

## Tuning rationale

- `--concurrency=1` - one fork. HF models + Ollama coordination not friendly to parallel forks under 12GB.
- `--max-tasks-per-child=4` - cycle worker every 4 tasks. Limits leak accumulation.
- `--max-memory-per-child=2500000` (KB) - 2.5GB cap. Worker recycles gracefully BEFORE kernel OOM-kill. See [[fixes/oom-sigkill]].

## Env

```
DJANGO_SETTINGS_MODULE=config.settings.dev
DATABASE_URL=postgres://...
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_VISION_MODEL=qwen2.5vl:3b
HF_TOKEN=...
PYTORCH_NO_CUDA_MEMORY_CACHING=1
OMP_NUM_THREADS=2          # bound PyTorch CPU threads
```

## Queues

- `default` - light analyzers (metadata, ela, audio_spectrogram)
- `ml` - heavy ML (ai_detector, llm_vision, llm_text, video_frame)
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

- `run_factcheck(text)` - async factcheck pipeline: spaCy NER -> DuckDuckGo search -> Ollama LLM assess -> Google Fact Check. Writes stage progress to Django cache (`fc:{task_id}`). Goes to `default` queue.

## Status messages

`ANALYZER_STATUS_MESSAGES` dict maps analyzer name -> user-facing string. Set on `submission.status_message` per-task so UI shows live "Analyzing image with vision AI...".

## Monitoring

See [[services/flower]].

## See also

- [[concepts/submission-pipeline]]
- [[fixes/oom-sigkill]]
- [[infrastructure/celery-tuning]]
