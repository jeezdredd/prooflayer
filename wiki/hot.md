# Hot Cache

Fast-load context for next session. Read me first.

## Last touched

- 2026-06-20: ROCm worker storage drift (3rd env-drift link). Even with AWS creds, worker still hit FileNotFoundError on local /app/media - because it ran `config.settings.dev` (forces FileSystemStorage) while backend runs `config.settings.prod` (S3/MinIO when AWS set; also REQUIRES SECRET_KEY env). Fix: celery_worker now `env_file: .env` (required:false) so every secret in .env injects literally - no `${}` interpolation pain for keys with `$`/special chars - plus `DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings.dev}`. Homelab .env must set `DJANGO_SETTINGS_MODULE=config.settings.prod` + `SECRET_KEY=...`. env_file auto-covers future drift.
- 2026-06-20: ROCm worker env-drift gotcha. The ROCm celery_worker is rebuilt MANUALLY (`WORKER_DOCKERFILE=backend/Dockerfile.rocm docker compose up celery_worker`), NOT via deploy.sh, so it only gets env that lives in `docker-compose.yml` + `.env` - it misses anything deploy.sh injects at runtime. Two failures chased: (1) submissions stuck `pending` = worker had default POSTGRES_PASSWORD, DB auth failed on `Submission.objects.get`. (2) submissions `failed` / all analyzers SKIPPED = worker had NO AWS_*/MinIO creds, so django-storages fell back to local FileSystemStorage and hit FileNotFoundError (files live in MinIO). Fix: forward AWS_ACCESS_KEY_ID/SECRET/BUCKET/ENDPOINT/CUSTOM_DOMAIN + GOOGLE_FACT_CHECK_KEY into celery_worker.environment, and keep real POSTGRES_PASSWORD + AWS creds in `/srv/prooflayer/current/.env` so manual rebuilds interpolate them. Lesson: any secret backend needs, the worker needs too - put them all in .env.
- 2026-06-20: GPU analyzer tasks hung forever in celery prefork worker. Root cause: HIP/ROCm is fork-unsafe (same as CUDA). billiard prefork forks pool child, first `model.to('cuda')` in child blocks on uninterruptible C call -> analyzer #1 stuck RUNNING, pipeline wedged. Non-GPU tasks (DB-only) ran fine in same child (3ms sanity), preload loaded models on cuda in standalone non-forked process -> proved GPU itself works, only fork breaks it. Fix: worker `--pool=solo` (runs task in MainProcess, valid HIP context, no fork) in docker-compose `command:` + Dockerfile.rocm CMD. Dropped concurrency/max-tasks/max-memory (no-op under solo). Alt = `--pool=threads --concurrency=1`. CPU escape hatch: `PROOFLAYER_FORCE_CPU=1` (honored by analyzers/_device.get_device).
- 2026-06-19: ROCm worker bringup gotchas fixed: HF model cache wasn't persisted (rocm/pytorch image has no volume), so every first submission hung the single-concurrency worker for 5-15 min on `from_pretrained` download. Added `hf_cache` named volume mounted at `/root/.cache/huggingface` + `HF_HOME=/root/.cache/huggingface` env. New `analyzers/preload_models` management command pre-pulls siglip / community_forensics / npr / clip ensemble on boot. Docker `command:` chains preload then celery so user submissions never trigger first download. Bumped `CELERY_TASK_TIME_LIMIT` 300->900, `SOFT_TIME_LIMIT` 240->720 to survive cold model loads. Added `--without-heartbeat --without-gossip --without-mingle` to celery to reduce broker chatter (concurrency=1 doesn't need cluster gossip).
- 2026-06-19: GPU/ROCm wiring. Dockerfile gets TORCH_INDEX_URL build arg (default cpu); `celery_worker` in compose mounts /dev/kfd + /dev/dri, group_add video+render, env HSA_OVERRIDE_GFX_VERSION + HIP_VISIBLE_DEVICES. Build worker with `TORCH_INDEX_URL=https://download.pytorch.org/whl/rocm6.0` to get GPU torch. AMD RX 6650 XT (gfx1032) supported on ROCm 6.x. New `analyzers/_device.py` (get_device/to_device/inputs_to_device); siglip_detector / community_forensics / npr_detector / clip_detector now load on cuda when available (ROCm masks as cuda), inputs moved per-call, outputs squeeze().cpu() before further processing. HF Trainer in retrain_detector auto-uses GPU - no code change there.
- 2026-06-19: VerdictOverrideView now marks submission `approved_for_training=True` + `verified_label=real/fake` when override verdict is authentic/fake/likely_fake. Without this, retrain query returned 0 samples even after manual review. Plus retrain task: accepts `triggered_by_id` (FK on RetrainRun, migration 0004) + `min_samples_override`; sends email to triggering user on success/skipped/failed. Frontend gets a "Force" checkbox to lower min_samples to 1 for testing on tiny datasets.
- 2026-06-19: Staff bypass throttles globally (new `common/throttling.py` Staff* subclasses set as DEFAULT_THROTTLE_CLASSES). UploadRateThrottle also bypasses staff. Admins no longer hit override/upload rate caps.
- 2026-06-19: Retrain trigger endpoint added: `POST /api/v1/analyzers/retrain/` (IsAdminUser) + `GET /api/v1/analyzers/retrain/runs/` for last 10. Frontend ReviewQueuePage now has media-type picker + "Run Retrain" button.
- 2026-06-19: Subscription gate Zap icon: text-iris bug (transparent gradient color) → text-violet-300.
- 2026-06-19: Pricing Internal tier: collapsed Active/Staff stack to single badge with priority, pr-16 on header row to prevent label/badge overlap.
- 2026-06-19: Factcheck v2 landed: Wikipedia lookup, confidence score per claim, top-3 web sources, claim->source highlight panel, PDF export, URL input mode, PDF/DOCX upload, qwen2.5:7b optional. See [[services/factcheck]].
- 2026-06-19: `backend/common/url_safety.py:validate_public_url` factored from `AnalyzeUrlView`; reused by factcheck URL fetch. SSRF guard now shared.
- 2026-06-19: Memory bank moved to Obsidian vault `claude-memory/` (was `~/.claude/projects/.../memory/`). Local dir frozen.
- 2026-06-18: Redis configured as Django cache backend (was LocMemCache - broke cross-process cache.get). See [[fixes/factcheck-cache]].
- 2026-06-18: Factcheck made async (Celery task + Redis stage cache). POST returns task_id, GET /status/ polls. See [[api/endpoints]].
- 2026-06-18: Resend switched to HTTP API (django-anymail) - no MX records needed, freed for Cloudflare Email Routing. See [[services/auth-email]].
- 2026-06-18: Staff/superuser bypass: no upload limits, skip IsVerifiedUser, skip SubscriptionGate. See [[services/backend]].
- 2026-06-18: toggle-public URL fixed (frontend sent underscore, backend expects hyphen). See [[fixes/toggle-public-url]].
- 2026-06-18: Pricing page: Internal tier card (staff only), Pro checkmarks fixed (text-iris = transparent), staff isCurrent logic.
- 2026-06-17: Browser extension built (MV3, Chrome + Firefox). See [[services/extension]].
- 2026-06-17: `analyze-url` endpoint added + `SubmissionStatusView` (AllowAny). See [[api/endpoints]].
- 2026-06-17: `AnonymousQuota` model - 5/day per IP for analyze-url. See [[models/AnonymousQuota]].
- 2026-06-17: Email service = Resend HTTP API. See [[services/auth-email]].

## Current dev state

- 12GB Docker ceiling. `qwen2.5vl:3b` active. `qwen2.5vl:7b` pulled but OOMs.
- AI ensemble = 2 models (dima806 + umm-maybe). Organika removed.
- Worker capped at `--max-memory-per-child=2500000`.
- Ollama `MAX_LOADED_MODELS=1`, `KEEP_ALIVE=2m`.
- All UI text uses ASCII hyphen, no em-dashes.
- Production at homelab Ubuntu server (192.168.8.112). Deploy: `~/deploy.sh prooflayer`.
- Docker project name: `deploy`. Containers: `deploy-backend-1`, `deploy-celery_worker-1`, etc.

## Extension status

Chrome/Firefox extension built and tested. Two open issues:
1. Login flow: `btn-login` opens `prooflayer.cloud/login` but JWT not persisted back to extension storage after login.
2. Anonymous quota: 5/day per IP drains fast during dev (each test = 1 use).

## Pending overhaul

[[concepts/detection-strategy-2026]] - 8-week roadmap to replace VLM-only pipeline with calibrated NPR + UniversalFakeDetect + ELA + perceptual hash + EXIF + C2PA + Qwen-as-explainer.

## Key files

- Pipeline dispatch: `backend/analyzers/tasks.py:dispatch_analysis`
- Aggregator: `backend/analyzers/aggregator.py:aggregate`
- Worker tuning: `docker-compose.yml:celery_worker.command`
- Frontend layout: `frontend/src/components/Layout.tsx`
- Shader: `frontend/src/components/ui/ShaderBackground.tsx`
- Status endpoint: `backend/api/system_views.py`

## Memory store

- User memory: `~/.claude/projects/-Users-sevastyan0107-PycharmProjects-prooflayer/memory/`
- Includes: no em-dashes, EU regions, celery app load rule, ollama Railway setup
