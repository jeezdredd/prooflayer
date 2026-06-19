# Hot Cache

Fast-load context for next session. Read me first.

## Last touched

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
