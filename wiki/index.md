# ProofLayer Memory Bank

Forensic content verification SaaS. Submit image/video/audio/text -> 7 independent analyzers cross-examine -> aggregated verdict published with raw evidence.

## Start here

- [[overview]] - what it does, who uses it
- [[architecture]] - system topology
- [[submission-pipeline]] - end-to-end request flow

## Services

- [[services/backend]] - Django 5.1 + DRF
- [[services/celery-workers]] - background analyzer pool
- [[services/ollama]] - local LLM inference
- [[services/postgres]] - relational store
- [[services/redis]] - broker + cache
- [[services/minio]] - S3-compatible blob store
- [[services/frontend]] - React + Vite
- [[services/flower]] - celery monitoring
- [[services/auth-email]] - JWT auth + email verification (Gmail SMTP)
- [[services/visit-tracking]] - Discord webhook notify on visit (IP + geo)
- [[services/backups]] - Nightly pg_dump -> MinIO, 14-day retention

## Detection strategy

- [[concepts/detection-strategy-2026]] - 8-week rebuild plan (parent)
- [[concepts/perceptual-provenance]] - Week 1: phash + PDQ + CLIP + C2PA + pgvector

## Analyzers (7 total)

- [[analyzers/_index]] - pipeline overview
- [[analyzers/metadata]] - EXIF / XMP signatures
- [[analyzers/ela]] - error level analysis (image splicing)
- [[analyzers/ai-ensemble]] - HF classifier vote (dima806 + umm-maybe)
- [[analyzers/siglip-detector]] - SigLIP-base binary classifier (Apache-2.0)
- [[analyzers/llm-vision]] - multimodal LLM (qwen2.5vl)
- [[analyzers/video-frames]] - uniform-sampled frames -> ensemble
- [[analyzers/audio-spectrogram]] - librosa spectral features
- [[analyzers/llm-text]] - text AI-authorship (qwen2.5:3b)

## Django models

- [[models/Submission]] - core unit of work
- [[models/AnalysisResult]] - per-analyzer evidence
- [[models/AnalyzerConfig]] - analyzer registry + weight + queue
- [[models/VerdictOverride]] - human review trail
- [[models/KnownFakeHash]] - SHA-256 blacklist seed
- [[models/User]] - custom auth user

## Concepts

- [[concepts/submission-pipeline]] - upload -> dispatch -> aggregate
- [[concepts/aggregation]] - weighted confidence -> final_score
- [[concepts/verdict-thresholds]] - score buckets -> labels
- [[concepts/skip-photo-check]] - bypass for video frames
- [[concepts/memory-budget]] - 12GB Docker constraints
- [[concepts/disagreement-needs-review]] - escalation rule

## Frontend

- [[frontend/routes]] - all React Router paths
- [[frontend/auth-flow]] - JWT in zustand + localStorage
- [[frontend/shader-bg]] - paper-design MeshGradient w/ kickoff anim
- [[frontend/sidebar-layout]] - 240px left nav

## Infrastructure

- [[infrastructure/docker-compose]] - 9 services topology
- [[infrastructure/env-vars]] - configurable knobs
- [[infrastructure/memory-limits]] - per-container budget
- [[infrastructure/celery-tuning]] - max-mem, max-tasks, OMP threads

## API

- [[api/endpoints]] - REST surface
- [[api/system-status]] - probe endpoint (GET /api/v1/system/status/)

## Known fixes / gotchas

- [[fixes/oom-sigkill]] - worker OOM during HF model load
- [[fixes/organika-broken]] - dropped from ensemble
- [[fixes/em-dash-purge]] - never use "-"
- [[fixes/photo-check-video]] - skip flag for video frames
- [[fixes/model-name-leak]] - stripped from evidence
