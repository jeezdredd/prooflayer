---
type: index
created: 2026-05-14
updated: 2026-06-14
---

# Analyzer Pipeline

Seven independent analyzers. Each implements `BaseAnalyzer`:

```python
class BaseAnalyzer:
    name: str
    version: str

    def supported_mime_types(self) -> list[str]: ...
    def analyze(self, file_path: str, metadata: dict) -> AnalysisOutput: ...
```

`AnalysisOutput`: `(confidence: float, verdict: str, evidence: dict)`.

Registered via [[models/AnalyzerConfig]] DB rows (admin-editable: weight, queue, timeout, is_active).

## Roster

| # | Name | Type | MIME | Queue | Weight | Notes |
|---|------|------|------|-------|--------|-------|
| 01 | [[analyzers/metadata]] | rule-based | image | default | 2.5 | EXIF/XMP signatures |
| 02 | [[analyzers/ela]] | rule-based | image | default | 1.0 | JPEG splice detection |
| 03 | [[analyzers/community-forensics]] | **probabilistic** | image | ml | **3.0** | ViT-S/16 NeurIPS 2024, main authority |
| 04 | [[analyzers/siglip-detector]] | **probabilistic** | image | ml | **2.0** | ViT deepfake classifier (raised from 1.5) |
| 05 | [[analyzers/npr-detector]] | **probabilistic** | image | ml | **0.5** | ViT deepfake detector (lowered from 1.5 - GAN-trained, blind to diffusion) |
| 06 | [[analyzers/llm-vision]] | rule-based | image | ml | 1.5 | LLaVA 7B vision analysis |
| 07 | [[analyzers/video-frames]] | mixed | video | ml | 2.0 | Sample frames -> image ensemble |
| 08 | [[analyzers/audio-spectrogram]] | rule-based | audio | default | 2.0 | Spectral artifact check |
| 09 | [[analyzers/llm-text]] | rule-based | text | ml | 2.5 | AI authorship classifier |

**Probabilistic** analyzers emit `evidence["ai_probability"]` and contribute raw probability to aggregation even when verdict is `inconclusive`.  
**Rule-based** analyzers emit verdict + confidence; aggregator uses `VERDICT_SCORES` mapping.

> [!change] 2026-06-14 Aggregator: probabilistic-always scoring
> CF, NPR, SigLIP now contribute to weighted sum from `valid_results` regardless of verdict. Previously `inconclusive` results were excluded - Gemini images scored `authentic` because only NPR (ai_prob=0.01) was in `decisive_results` while CF (ai_prob=0.40) and SigLIP (ai_prob=0.64) were silently dropped.

> [!change] 2026-06-14 `authentic_edited` verdict
> Aggregator emits `authentic_edited` when `final_score < 0.30` (no AI signal) but ELA or metadata returns `suspicious`/`fake`. Frontend shows "REAL · EDITED" banner with explanation.

> [!deprecated] [[analyzers/ai-ensemble]] (dima806 + umm-maybe) dropped 2026-05-31.  
> Replaced by CommunityForensics + NPR detector. See [[concepts/detection-strategy-2026]].

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
- `npr_detector.py`
- `llm_image_analyzer.py`
- `video_analyzer.py`
- `audio_analyzer.py`
- `llm_analyzer.py` (text)

> [!gap] Multi-modal video
> Video MIME routes to [[analyzers/video-frames]] only. Audio track not extracted -> audio-spectrogram skipped. Gap to close post-diploma.
