---
type: fix
created: 2026-05-09
---

# Fix: Organika/sdxl-detector dropped

**Symptom:** `AI detector model Organika/sdxl-detector failed: Can't load the model... make sure 'Organika/sdxl-detector' is the correct path...`

**Cause:** HF model weights unavailable / format mismatch from upstream HF repo. Tried to download ~5GB at runtime, contributed to OOM cascade.

**Fix:** Removed from `ENSEMBLE_MODELS` in `backend/analyzers/implementations/clip_detector.py`.

Ensemble now:
```python
ENSEMBLE_MODELS = [
    "dima806/ai_vs_real_image_detection",
    "umm-maybe/AI-image-detector",
]
```

## Note (research finding)

Per fresh 2026-05-14 research synthesis: **Organika/sdxl-detector also has cc-by-nc-3.0 licensing** - cannot ship in commercial SaaS even if it worked. Apache-2.0 substitute: `prithivMLmods/deepfake-detector-model-v1` (SigLIP-base, ~94% on author's eval).

Also: `umm-maybe/AI-image-detector` is from the VQGAN era and obsolete on modern generators. Should be replaced.

See [[concepts/detection-strategy-2026]] for full overhaul plan.
