# Ingest Log

Newest at top.

## [2026-09-04] roster-drift-visibility | Analyzer roster drift check, probe, Makefile targets

- Source: `.env`, `docker-compose.yml`, `deploy/compose.prod.yml`, `Makefile`, `backend/api/system_views.py`, `backend/users/checks.py` (pattern)
- Summary: host-side `seed_analyzers` failure traced to compose hostnames in `.env`; added `analyzers/roster.py`, `analyzers.W001` system check, `/system/status` `analyzers` probe + StatusPage row, `seed_analyzers --check`, four Makefile targets; fixed seed never re-activating deactivated rows
- Pages updated: [[api/system-status]], [[analyzers/_index]], [[hot]]
- Headline: the roster only reconciles when the backend container restarts; every weight rebalance so far was invisible on a worker-only rebuild

## [2026-09-04] npr-real-implementation | Real NPR built, measured, benched; disagreement rule reweighted

- Source: `github.com/chuangchuangtan/NPR-DeepfakeDetection` (networks/resnet.py, data/datasets.py, HF demo app.py), authors' checkpoint `model_epoch_last_3090.pth`, `eval_detectors` on dataset/hf
- Summary: old `npr_detector` was a face ViT -> renamed `face_deepfake_detector`; real NPR implemented and verified against the authors' demo, then measured AUC 0.499 on diffusion output and left unseeded; aggregator disagreement now weight-share based
- Pages created: [[analyzers/face-deepfake-detector]]
- Pages updated: [[analyzers/npr-detector]] (rewritten), [[analyzers/_index]] (roster refresh, 12 analyzers), [[concepts/aggregation]], [[concepts/detector-evaluation]], [[concepts/detection-strategy-2026]], [[fixes/audit-2026-08]], [[services/celery-workers]], [[index]], [[hot]]
- Headline: a correctly implemented SOTA-2024 detector was worse than useless on 2026 diffusion imagery; the ensemble rule that let it do damage was the real defect

## [2026-08-19] system-audit | Full-stack audit: detection, security, reliability

- Source: live read of `backend/` (analyzers, content, common, provenance, config) + HF model configs + 2026 detection benchmark literature
- Summary: 11 correctness bugs and 3 security issues found and fixed; suite 33 failed/133 passed -> 301 passed
- Pages created: [[fixes/audit-2026-08]]
- Pages updated: [[concepts/aggregation]], [[hot]]
- Headline: aggregator silently zero-weighted `llm_vision`; EXIF sub-IFD never read so camera-signature was unreachable; video analysis broken on GPU; C2PA extraction dead since the c2pa-python 0.5 API change

## [2026-05-14] memory-bank-creation | Full ProofLayer wiki bootstrap

- Source: live read of `/Users/sevastyan0107/PycharmProjects/prooflayer/` (backend/, frontend/, docker-compose.yml, .env.example, models, services)
- Summary: First full wiki memory bank for the project
- Pages created (30+):
  - Index: [[index]], [[overview]], [[architecture]], [[hot]]
  - Services: [[services/backend]], [[services/celery-workers]], [[services/ollama]], [[services/postgres]], [[services/redis]], [[services/minio]], [[services/flower]], [[services/frontend]]
  - Analyzers: [[analyzers/_index]], [[analyzers/metadata]], [[analyzers/ela]], [[analyzers/ai-ensemble]], [[analyzers/llm-vision]], [[analyzers/video-frames]], [[analyzers/audio-spectrogram]], [[analyzers/llm-text]]
  - Models: [[models/Submission]], [[models/AnalysisResult]], [[models/AnalyzerConfig]], [[models/VerdictOverride]], [[models/KnownFakeHash]], [[models/User]]
  - Concepts: [[concepts/submission-pipeline]], [[concepts/aggregation]], [[concepts/verdict-thresholds]], [[concepts/skip-photo-check]], [[concepts/memory-budget]], [[concepts/detection-strategy-2026]]
  - Frontend: [[frontend/routes]], [[frontend/auth-flow]], [[frontend/shader-bg]], [[frontend/sidebar-layout]]
  - Infrastructure: [[infrastructure/docker-compose]], [[infrastructure/env-vars]]
  - API: [[api/endpoints]], [[api/system-status]]
  - Fixes: [[fixes/oom-sigkill]], [[fixes/organika-broken]], [[fixes/model-name-leak]], [[fixes/em-dash-purge]]
- Key insight: research synthesis from user (filed as [[concepts/detection-strategy-2026]]) identifies VLM-as-oracle as structurally wrong. 8-week roadmap to rebuild as calibrated ensemble.
