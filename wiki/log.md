# Ingest Log

Newest at top.

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
