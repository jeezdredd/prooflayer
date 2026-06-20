---
type: analyzer
created: 2026-06-20
---

# custom_detector

Retrained ViT image detector. Highest aggregation weight (**3.5**) - the project's own continuously-improving model.

Source: `backend/analyzers/implementations/custom_detector.py`. Seeded in `seed_analyzers.py` (queue `ml`, timeout 180).

## Model source

- Loads from `RETRAIN_MODEL_DIR/image` (default `/root/.cache/huggingface/prooflayer-retrained/image`) when a `config.json` exists there.
- Falls back to `Nahrawy/AIorNot` when no retrained model is present.
- Load uses `use_safetensors=True` with a fallback (torch 2.3 on ROCm blocks pickle `.bin`, CVE-2025-32434). Runs on CPU (no device move).

Output: continuous `ai_probability` -> verdict via thresholds (>=0.85 fake, >=0.65 suspicious, <0.15 / <0.35 authentic, else inconclusive). `evidence.retrained` flags whether the retrained model or the fallback was used.

## How it gets trained

1. Staff use the [[services/extension]] / review queue to override verdicts. `VerdictOverrideView` sets `submission.approved_for_training=True` + `verified_label=real|fake` (authentic->real, fake/likely_fake->fake).
2. `POST /api/v1/analyzers/retrain/` (admin-only, `force` + `epochs` options) dispatches `run_weekly_retrain` which fine-tunes from those approved samples and writes a new model dir (safetensors).
3. Next inference reloads the new model into the in-process cache (path change detected).

See [[services/celery-workers]] (retrain task) and [[api/endpoints]] (retrain endpoints).

## Notes

- GPU: this analyzer currently runs on CPU even on the ROCm worker (no `to_device`); the retrain Trainer itself uses the GPU. See [[services/gpu-rocm]].
- Was previously undocumented despite being the highest-weighted analyzer.
