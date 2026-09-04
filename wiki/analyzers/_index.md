---
type: index
created: 2026-05-14
updated: 2026-09-04
---

# Analyzer Pipeline

Nine analyzers seeded as [[models/AnalyzerConfig]] DB rows (`backend/analyzers/management/commands/seed_analyzers.py`). Each implements `BaseAnalyzer`:

```python
class BaseAnalyzer:
    name: str
    version: str

    def supported_mime_types(self) -> list[str]: ...
    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput: ...
```

`AnalysisOutput`: `(confidence: float, verdict: str, evidence: dict)`.

Registered via [[models/AnalyzerConfig]] DB rows (admin-editable: weight, queue, timeout, is_active).

The roster, its weights and the aggregation rules are versioned together as [[concepts/tribunal]]
(`analyzers/ensemble.py`); every submission detail response and the status probe carry the
version label and a roster fingerprint.

> [!warning] Rows only change when `seed_analyzers` runs
> That happens on backend container boot (`docker-compose.yml`, `deploy/compose.prod.yml`) -
> **not** on a worker-only rebuild, and not by editing this file. Until then the DB keeps the
> old weights and any renamed analyzer keeps running under its old class path.
> - Detect: `/system/status` -> `services.analyzers` (`down` on drift), `manage.py check`
>   (`analyzers.W001`), `make roster-check` / `manage.py seed_analyzers --check` (exit 1).
> - Fix: `make seed-analyzers` (compose), `make seed-analyzers-host` (uv from the host - plain
>   `python manage.py` fails because `.env` points at the compose hostnames `db`/`redis`),
>   `make seed-analyzers-server` (prod).
> - `seed_analyzers` also re-activates expected rows now; before 2026-09-04 a row that had been
>   deactivated stayed deactivated forever. Logic in `analyzers/roster.py`.

## Roster

Weights as of Tribunal 1.1 (2026-09-04), after the measured rebalance in [[fixes/audit-2026-08]].

| # | Name | Type | MIME | Queue | Weight | Notes |
|---|------|------|------|-------|--------|-------|
| 01 | [[analyzers/metadata]] | rule-based | image | default | 1.5 | EXIF sub-IFD, PNG `parameters`, XMP, C2PA `trainedAlgorithmicMedia`. Lowered from 2.5: EXIF is forgeable |
| 02 | [[analyzers/ela]] | manipulation-only | image | default | 0.75 | Never votes on the AI axis (measured inverted); feeds `authentic_edited` via `manipulation_suspected` |
| 03 | [[analyzers/community-forensics]] | **probabilistic** | image | ml | **3.5** | ViT-S/16 NeurIPS 2024. AUC 1.000 diffusiondb / 0.977 OpenFake; raw score **calibrated** since 2026-09-04 |
| 06 | [[analyzers/custom_detector]] | **probabilistic** | image | ml | **3.5** | Retrained 2026-09-04 on the CF backbone with 20 current generators: AUC **0.993** held-out. Back to 3.5 in Tribunal 1.1, this time measured |
| 07 | [[analyzers/ai-ensemble]] (`ai_detector`) | **probabilistic** | image | ml | 1.0 | dima806 + umm-maybe with a photographic gate. AUC 0.914 diffusiondb, 0.668 current generators; lowered from 1.5 in Tribunal 1.1 |
| 08 | [[analyzers/llm-vision]] | rule-based | image | ml | 1.5 | Ollama vision. Contributed **zero** weight until 2026-08-19 |
| 09 | [[analyzers/video-frames]] | **probabilistic** | video | ml | 2.0 | Frames sampled across the whole clip -> CF; emits median `ai_probability` |
| 10 | [[analyzers/audio-spectrogram]] | rule-based + prob | audio | ml | 2.0 | Spectral flags; now also emits `ai_probability` |
| 11 | [[analyzers/llm-text]] | rule-based | text | ml | 2.5 | AI authorship classifier |

Not seeded:
- [[analyzers/npr-detector]] - real NPR (CVPR 2024), correct and tested, but AUC 0.499 on diffusion
  output. Kept as an opt-in GAN-era detector.
- [[analyzers/face-deepfake-detector]] - `Wvolf/ViT_Deepfake_Detection`, the model that used to be
  called `npr_detector`. AUC 0.688 on diffusiondb, **0.181** on OpenFake. Removed 2026-09-04.
- [[analyzers/siglip-detector]] - `prithivMLmods/Deep-Fake-Detector-v2-Model`. AUC **0.323** and a
  **35% false-positive rate** on real photos (21/60 at p>=0.75). Even at weight 0.5 it was one of the
  two voters behind every real-photo `needs_review`. Removed 2026-09-04; keep the module for a
  face-swap set if one ever lands.

Real model ids: community_forensics=`buildborderless/CommunityForensics-DeepfakeDet-ViT`, face_deepfake_detector (not seeded)=`Wvolf/ViT_Deepfake_Detection`, npr_detector (not seeded)=authors' `model_epoch_last_3090.pth` (sha256-pinned). Torch detectors load on `cuda` when available (AMD ROCm worker, see [[services/gpu-rocm]]) via `analyzers/_device.py`.

**Probabilistic** is decided per result from the evidence payload (`ai_probability` or
`ai_probability_avg`), not from a name list - see [[concepts/aggregation]].
**Rule-based** analyzers emit verdict + confidence; aggregator uses `VERDICT_SCORES` mapping.

> [!change] 2026-09-04 Weighted disagreement
> `needs_review` now requires the lighter camp to hold >= 30% of the confident-voter weight, not
> just two heads. Two saturated low-weight detectors could otherwise manufacture review against
> a 3.5 + 1.5 + 1.5 consensus - which is exactly what real NPR did on 27/60 AI images.

> [!change] 2026-08-19 Probability sourced from evidence
> The hardcoded `PROBABILISTIC_ANALYZERS` set silently zero-weighted `llm_vision` and discarded
> `custom_detector` / `ai_detector` probabilities. See [[fixes/audit-2026-08]].

> [!change] 2026-06-14 `authentic_edited` verdict
> Aggregator emits `authentic_edited` when `final_score < 0.30` (no AI signal) but a
> manipulation analyzer flags the image. Frontend shows "REAL · EDITED" banner with explanation.

## Dispatch

`analyzers/tasks.py:dispatch_analysis` builds a Celery `chord(group(run_analyzer for each config))` -> `aggregate_verdicts` callback. See [[concepts/submission-pipeline]].

> [!note] Chord loss on worker restart
> If the worker restarts mid-chord, Redis chord state is lost and `aggregate_verdicts` never fires. `rescue_stuck_submissions` beat task (every 300s) detects submissions stuck in `processing` for >10 min and force-calls `aggregate_verdicts` on them.

Each `run_analyzer` task:

1. Loads class via `analyzers/registry.py:load_analyzer_class`
2. MIME guard
3. Updates `submission.status_message`
4. Pulls file from MinIO (`storage_utils.local_file`)
5. Calls `analyzer.analyze(...)`
6. Creates [[models/AnalysisResult]] row
7. Excepts -> creates row with `verdict=error`

## Source files

`backend/analyzers/implementations/`:
- `metadata_analyzer.py`
- `ela_analyzer.py`
- `community_forensics.py`
- `siglip_detector.py`
- `face_deepfake_detector.py` (was `npr_detector.py` until 2026-09-04)
- `npr_detector.py` (real NPR, not seeded)
- `custom_detector.py` (retrained)
- `clip_detector.py` (`ai_detector` ensemble)
- `llm_image_analyzer.py`
- `video_analyzer.py`
- `audio_analyzer.py`
- `llm_analyzer.py` (text)

Offline measurement: `manage.py eval_detectors`, see [[concepts/detector-evaluation]].

> [!gap] Multi-modal video
> Video MIME routes to [[analyzers/video-frames]] only. Audio track not extracted -> audio-spectrogram skipped. Gap to close post-diploma.
