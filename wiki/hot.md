# Hot Cache

Fast-load context for next session. Read me first.

## Last touched

- 2026-05-14: Created full memory bank. See [[index]].
- 2026-05-14: Filed research synthesis [[concepts/detection-strategy-2026]] (Qwen-as-oracle is wrong; rebuild as calibrated ensemble).
- 2026-05-13: Em-dash purge complete. See [[fixes/em-dash-purge]].
- 2026-05-10: skip_photo_check flag added. See [[concepts/skip-photo-check]].
- 2026-05-09: Organika dropped. See [[fixes/organika-broken]]. Model name leak stripped. See [[fixes/model-name-leak]].

## Current dev state

- 12GB Docker ceiling. `qwen2.5vl:3b` active. `qwen2.5vl:7b` pulled but OOMs.
- AI ensemble = 2 models (dima806 + umm-maybe). Organika removed.
- Worker capped at `--max-memory-per-child=2500000`.
- Ollama `MAX_LOADED_MODELS=1`, `KEEP_ALIVE=2m`.
- All UI text uses ASCII hyphen, no em-dashes.

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
