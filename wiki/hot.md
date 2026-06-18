# Hot Cache

Fast-load context for next session. Read me first.

## Last touched

- 2026-06-17: Browser extension built (MV3, Chrome + Firefox). See [[services/extension]].
- 2026-06-17: `analyze-url` endpoint added + `SubmissionStatusView` (AllowAny). See [[api/endpoints]].
- 2026-06-17: `AnonymousQuota` model - 5/day per IP for analyze-url. See [[models/AnonymousQuota]].
- 2026-06-17: Email service = Resend (smtp.resend.com). Replaced Gmail SMTP. See [[services/auth-email]].
- 2026-06-17: All domain refs changed prooflayer.com -> prooflayer.cloud everywhere (frontend, extension).
- 2026-05-14: Created full memory bank. See [[index]].
- 2026-05-14: Filed research synthesis [[concepts/detection-strategy-2026]] (Qwen-as-oracle is wrong; rebuild as calibrated ensemble).

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
