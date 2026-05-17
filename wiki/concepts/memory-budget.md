---
type: concept
created: 2026-05-14
---

# 12GB Memory Budget

Dev environment runs on macOS host with Docker Desktop allocated **12GB total** across all containers.

## Steady-state usage (idle)

| Container | RAM |
|-----------|-----|
| postgres | ~20 MB |
| redis | ~7 MB |
| minio | ~80 MB |
| flower | ~95 MB |
| frontend (vite) | ~130 MB |
| backend (django dev) | ~380 MB |
| celery_worker (idle) | ~140 MB |
| ollama (no model loaded) | ~4.4 GB (runtime + cached layers) |
| **total idle** | ~5.3 GB |

Free headroom idle: ~6.4 GB.

## Peak during submission

When image submission runs all analyzers + ollama spins up vision:

- celery_worker: 140 -> 2-3 GB (HF transformers + 1 cached model)
- ollama: 4.4 -> 4.4 + 3.2 GB (qwen2.5vl:3b loaded) = ~7.6 GB
- Other: ~700 MB

Peak total: ~11-12 GB. **At ceiling.** Any spike kills worker -> [[fixes/oom-sigkill]].

## Mitigations

- `OLLAMA_MAX_LOADED_MODELS=1` - text and vision NEVER coexist
- `OLLAMA_KEEP_ALIVE=2m` - idle model auto-unloads
- Vision model = `qwen2.5vl:3b` (3.2GB), not `:7b` (6.0GB)
- HF ensemble `_MAX_CACHED=1` - one model at a time, gc on eviction
- Celery `--max-memory-per-child=2500000` graceful restart
- `OMP_NUM_THREADS=2` bounds PyTorch CPU mem
- Frontend `--max-tasks-per-child=4` - cycle worker

## Scaling out

User has Ubuntu Linux box planned. With more RAM + optional NVIDIA GPU:
- Drop `OLLAMA_MAX_LOADED_MODELS` (let multiple coexist)
- Run `qwen2.5vl:7b` for better vision quality
- Add `qwen2.5:14b` for text
- Restore higher concurrency
- Drop memory caps

See [[infrastructure/memory-limits]].
