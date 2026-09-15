# Ingest Log

Newest at top.

## [2026-09-15] tribunal-1.2-calibration | Per-model calibration file for the retrained detector

- Source: regenerated eval JSON on dataset/openfake_test, generator+real split holdout
- Pages updated: [[concepts/tribunal]], [[analyzers/custom_detector]], [[hot]]

## [2026-09-15] presigned-media-fix | Signed media URLs for a public endpoint; Caddy media block

- Source: prod `.env`, live `default_storage.url()` output on the server, storages 1.14.6 `url()`, `deploy/caddy.snippet`
- Pages created: [[fixes/presigned-media-public-endpoint]]
- Pages updated: [[hot]]

## [2026-09-04] tribunal-1.1-retrain | Ensemble named and versioned; custom_detector retrained on 2026 generators

- Source: `retrain_detector` run (CF backbone, openfake + hf), `fetch_openfake --start-row-group 6` + `dedupe_dataset` for a held-out test, eval JSONs (eval9 baseline, eval10 retrained, eval12/13 Tribunal 1.1 confirm), offline weight/rule simulation with the real `aggregate()`
- Summary: Tribunal identity (name, version, fingerprint) in API/status/landing; retrained member AUC 0.711 -> 0.993 held-out; lone-voter exception (share >= 50%, p >= 0.9) + weights CF 3.5 / custom 3.5 / ai 1.0; ensemble caught 23% -> 71% on unseen modern generators with 0 real photos called fake
- Commands added: `retrain_detector --extra-dir/--base-model`, `dedupe_dataset`, `fetch_openfake --start-row-group`, `make ship-retrained`
- Pages created: [[concepts/tribunal]]
- Pages updated: [[analyzers/custom_detector]] (rewritten), [[concepts/aggregation]], [[concepts/detector-evaluation]], [[analyzers/_index]], [[api/system-status]], [[frontend/routes]], [[fixes/audit-2026-08]], [[hot]]
- Headline: 130 seconds of fine-tuning on the right backbone did more than any threshold could - and the rule that let it count had to be shaped by the 5% of real photos the new model over-scores

## [2026-09-04] modern-generators-openfake | OpenFake eval, CF calibration, two face models unseeded

- Source: `ComplexDataLab/OpenFake` core/test parquet (150 real + 236 AI, 20 generators), eval JSONs, arXiv 2602.07814 benchmark for framing
- Summary: measured the ensemble on 2026 generators for the first time (41% of AI called authentic); found CF ranks fine (AUC 0.977) but is miscalibrated; shipped a holdout-validated piecewise-linear calibration; unseeded siglip (35% real-photo FP) and face_deepfake (AUC 0.181); ensemble AUC 0.808 -> 0.890, acc 0.627 -> 0.777, real->fake 0
- Commands added: `fetch_openfake` (memory-bounded parquet sampler), per-generator table in `eval_detectors`
- Pages updated: [[fixes/audit-2026-08]], [[analyzers/community-forensics]], [[analyzers/face-deepfake-detector]], [[analyzers/siglip-detector]], [[analyzers/_index]] (9 seeded), [[concepts/aggregation]], [[concepts/detector-evaluation]], [[hot]]
- Headline: a detector that separates 2022 output perfectly read 41% of 2026 output as real - and the fix was a threshold map with zero measured false positives, not a new model. flux.2 and sora-2 remain invisible.

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
