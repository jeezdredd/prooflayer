---
type: service
created: 2026-06-20
---

# GPU / ROCm worker

The homelab Ubuntu server has an AMD **Radeon RX 6700S** (Navi 23, gfx1031, 8 GB). The Celery worker runs torch detectors on it via ROCm; everything else (backend, db, redis, ollama) stays as-is.

## Image

- `backend/Dockerfile.rocm` - base `rocm/pytorch:rocm6.2_ubuntu22.04_py3.10_pytorch_release_2.3.0` (ROCm runtime + torch 2.3 preinstalled). It strips `torch`/`torchvision`/`torchaudio` from `pyproject.toml` before `uv pip install` so the base image's ROCm torch survives.
- Opt-in per build: `WORKER_DOCKERFILE=backend/Dockerfile.rocm`. Default worker image stays CPU (`backend/Dockerfile`).

## docker-compose `celery_worker`

```yaml
devices: [ /dev/kfd, /dev/dri ]
group_add: [ "${RENDER_GID:-991}", "${VIDEO_GID:-44}" ]   # numeric HOST gids, not container names
env_file: [ { path: .env, required: false } ]
environment:
  - HSA_OVERRIDE_GFX_VERSION=${HSA_OVERRIDE_GFX_VERSION:-}   # 10.3.0 for gfx1031
  - HIP_VISIBLE_DEVICES=${HIP_VISIBLE_DEVICES:-0}
volumes:
  - hf_cache:/root/.cache/huggingface
```

Host needs only the amdgpu kernel driver (built into Ubuntu) exposing `/dev/kfd` + `/dev/dri`; ROCm userspace lives in the image, so no host ROCm install (handy on Ubuntu 26.04 where AMD has no repo yet).

## Bring-up

```bash
echo "RENDER_GID=$(getent group render | cut -d: -f3)" >> .env
echo "VIDEO_GID=$(getent group video | cut -d: -f3)" >> .env
echo "HSA_OVERRIDE_GFX_VERSION=10.3.0" >> .env
echo "WORKER_DOCKERFILE=backend/Dockerfile.rocm" >> .env
WORKER_DOCKERFILE=backend/Dockerfile.rocm docker compose -p deploy build celery_worker
docker compose -p deploy up -d --force-recreate celery_worker
docker compose -p deploy exec celery_worker python -c "import torch; print(torch.cuda.is_available(), torch.version.hip)"
```

`analyzers/_device.py:get_device()` returns `cuda` when `torch.cuda.is_available()` (ROCm masks as cuda), else `cpu`; `PROOFLAYER_FORCE_CPU=1` forces CPU. siglip / community_forensics / npr / clip_detector load on cuda and move inputs/outputs per-call.

## Hard-won gotchas (this chain bit us repeatedly)

1. **Fork-unsafe GPU** - celery default prefork forks pool children; first `model.to('cuda')` in a child hangs forever. Fix: `--pool=solo` (no fork). See [[services/celery-workers]].
2. **torch CPU clobber** - `uv pip install -r pyproject` reinstalled torch from PyPI CPU wheel over the ROCm one. Fix: strip torch lines before install.
3. **GID mismatch** - `/dev/kfd` owned by host render gid 991; `group_add: render` resolved the *container* gid. Fix: pass numeric host gids.
4. **env-drift** (manual rebuild misses deploy.sh env): missing POSTGRES_PASSWORD -> DB auth fail (stuck pending); missing AWS creds -> local FileSystemStorage -> FileNotFoundError; `config.settings.dev` -> local storage. Fix: `env_file: .env` + `DJANGO_SETTINGS_MODULE=config.settings.prod`.
5. **CVE-2025-32434** - torch 2.3 blocks `torch.load` on pickle `.bin`. Use `use_safetensors=True` everywhere (analyzers, retrain base model, CLIP provenance).
6. **HF cache not persisted** - first submission downloaded GBs inside the single-concurrency worker. Fix: `hf_cache` volume + `preload_models` on boot.

## Related

[[services/celery-workers]] · [[analyzers/custom_detector]] · [[concepts/detection-strategy-2026]] · [[hot]]
