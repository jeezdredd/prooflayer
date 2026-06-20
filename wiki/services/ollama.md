---
type: service
created: 2026-05-14
---

# Ollama (Local LLM)

Local LLM inference server. Hosts text + vision models. Called via HTTP from celery workers.

## Container

```yaml
ollama:
  image: ollama/ollama
  ports: ["11434:11434"]
  volumes:
    - ollama_data:/root/.ollama
  environment:
    - OLLAMA_MAX_LOADED_MODELS=1
    - OLLAMA_KEEP_ALIVE=2m
```

Healthcheck: `ollama list`.

## Init container

`ollama_init` (one-shot, runs after ollama healthy):

```
ollama pull qwen2.5:3b && ollama pull qwen2.5vl:3b
```

Pulls into shared volume so subsequent `ollama serve` finds them cached.

## Models in volume

| Model | Size | Active | Notes |
|-------|------|--------|-------|
| `qwen2.5:3b` | 1.9 GB | yes | text LLM (`OLLAMA_MODEL`) |
| `qwen2.5vl:3b` | 3.2 GB | yes | vision LLM (`OLLAMA_VISION_MODEL`) |
| `qwen2.5vl:7b` | 6.0 GB | no | pulled but OOMs on 12GB Docker |
| `moondream` | 1.7 GB | no | legacy original vision default |

## Critical env

- `OLLAMA_MAX_LOADED_MODELS=1` - only one model resident at a time. Text and vision swap.
- `OLLAMA_KEEP_ALIVE=2m` - idle model unloads after 2 min, freeing RAM.

Without these, both text+vision would coexist (~5GB) + HF ensemble in worker (~1GB) + Postgres/Redis/Django (~2GB) = bumps against 12GB. See [[concepts/memory-budget]].

## API endpoints used

- `POST /api/generate` (with `images: [b64]` for vision)
- `GET /api/tags` (list available models) - used by [[api/system-status]]
- `GET /api/ps` (currently loaded models) - status page

## Cold load latency

First call after `OLLAMA_KEEP_ALIVE` timeout = load weights from disk to RAM:

- 3b text: ~3-5s
- 3b vision: ~10-15s
- 7b vision (if active): ~60s+ on CPU

User-facing: UploadProgress shows rotating tips ("Cold-loading vision model...") to hide this.

## Deployment (homelab)

Self-hosted on the Ubuntu homelab. `docker-compose.yml` `ollama` service mounts `ollama_data:/root/.ollama`; `ollama_init` pulls `qwen2.5:3b`, `qwen2.5vl:3b`, and best-effort `qwen2.5:7b` on boot. Production sets `OLLAMA_VISION_MODEL=qwen2.5vl:3b`.

> [!note] vision model default
> `config.settings.base.py` hardcodes `OLLAMA_VISION_MODEL` default `llava:7b`, but compose overrides it (`moondream` for the backend service default, `qwen2.5vl:3b` for the worker). Production env sets `qwen2.5vl:3b` explicitly - the base default is never used in deployed envs.

(Railway is retired; the project moved to the homelab Ubuntu server - see [[services/gpu-rocm]].)

## See also

- [[analyzers/llm-vision]]
- [[analyzers/llm-text]]
- [[concepts/memory-budget]]
- [[infrastructure/env-vars]]
