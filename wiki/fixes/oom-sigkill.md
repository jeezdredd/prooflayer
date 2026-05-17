---
type: fix
created: 2026-05-14
---

# Fix: OOM SIGKILL on celery worker

**Symptom:** `Process 'ForkPoolWorker-N' pid:N exited with 'signal 9 (SIGKILL)'`. Celery worker dies mid-submission.

**Cause:** 12GB Docker total ceiling. Peak memory during HF model load + Ollama vision-model load + Django/Postgres/Redis baseline exceeds limit. Kernel OOM-killer fires SIGKILL.

**Sequence that triggers it:**
1. Submission lands, dispatch_analysis fans out
2. Celery worker imports HF transformers (~1.5GB Python+PyTorch overhead)
3. Loads AI ensemble model (~500MB)
4. Concurrently Ollama spins up vision model (3.2GB for qwen2.5vl:3b)
5. Worker peaks during this window -> SIGKILL

## Fixes applied

In `docker-compose.yml` celery_worker:

```yaml
command: >
  celery -A config.celery worker --loglevel=info
  -Q default,ml,reports
  --concurrency=1
  --max-tasks-per-child=4
  --max-memory-per-child=2500000
environment:
  - OMP_NUM_THREADS=2
  - PYTORCH_NO_CUDA_MEMORY_CACHING=1
```

- `--max-memory-per-child=2500000` (2.5GB KB) - celery recycles worker BEFORE kernel OOM-kill
- `--max-tasks-per-child=4` - frequent cycle limits leak accumulation
- `OMP_NUM_THREADS=2` - bound PyTorch CPU thread count

In `clip_detector.py`:

```python
import gc

def _load_model(name):
    if eviction_needed:
        del _model_cache[evict_key]
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
```

In Ollama env:

```yaml
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_KEEP_ALIVE=2m
```

Text and vision models swap; idle model unloads in 2 min.

## Outstanding

If single task itself peaks above 2.5GB worker-internal mem, can still SIGKILL. Mitigations:
- Drop to `qwen2.5vl:3b` (done) instead of `:7b`
- Consider moving HF inference to dedicated FastAPI container (research suggests this)

See [[concepts/memory-budget]].
