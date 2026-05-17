---
type: overview
created: 2026-05-14
---

# ProofLayer Overview

Diploma project. Forensic content verification SaaS.

## What

User uploads image / video / audio / text. System runs N independent analyzers in parallel. Each publishes raw evidence + verdict + confidence. Aggregator weighted-averages into `final_score` (0-1) and `final_verdict` label.

> [!key-insight]
> "Confidence ≠ certainty". Each analyzer outputs evidence JSON, not just a number. Disagreement -> needs_review (not silenced).

## Stack

- Backend: Django 5.1 + DRF + drf-spectacular
- Async: Celery 5.4 + Redis 7
- DB: Postgres 16
- Storage: MinIO (S3-compat) or filesystem in dev
- LLM: Ollama (qwen2.5:3b text, qwen2.5vl:3b vision)
- Frontend: React 18 + Vite 6 + Tailwind 3 + motion (formerly framer-motion) + react-router-dom 7 + zustand + tanstack query
- Background shader: `@paper-design/shaders-react` MeshGradient
- Icons: `lucide-react`

## Pages

See [[frontend/routes]] for full list. Headline pages:

- `/` [[frontend/routes]] landing (auth-aware CTA)
- `/upload` evidence submission ([[concepts/submission-pipeline]])
- `/dashboard` case registry table
- `/results/:id` per-submission verdict + [[analyzers/_index|analyzer timeline]]
- `/factcheck` text claim extraction
- `/status` live service health probes

## Verdict labels

`authentic` | `suspicious` | `inconclusive` | `likely_fake` | `fake` | `needs_review`. See [[concepts/verdict-thresholds]].

## Constraints (current dev)

12GB Docker memory ceiling. Forces:
- Vision model = `qwen2.5vl:3b` (~3.2GB), not `:7b`
- HF ensemble = 2 models (dima806 + umm-maybe). Organika removed -> [[fixes/organika-broken]]
- `OLLAMA_MAX_LOADED_MODELS=1` + `OLLAMA_KEEP_ALIVE=2m` so text/vision swap not coexist
- Celery `--max-memory-per-child=2500000` graceful restart before OOM kill

Future: Linux server with GPU -> see [[infrastructure/memory-limits]].
