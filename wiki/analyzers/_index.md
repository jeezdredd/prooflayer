---
type: index
created: 2026-05-14
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

| # | Name | Class | MIME | Queue | Weight | Notes |
|---|------|-------|------|-------|--------|-------|
| 01 | [[analyzers/metadata]] | `MetadataAnalyzer` | image | default | low | EXIF/XMP signatures |
| 02 | [[analyzers/ela]] | `ELAAnalyzer` | image | default | low | JPEG splice detection |
| 03 | [[analyzers/ai-ensemble]] | `AIImageDetector` | image | ml | high | 2-model HF vote |
| 04 | [[analyzers/llm-vision]] | `LLMImageAnalyzer` | image | ml | high | Vision LLM examines |
| 05 | [[analyzers/video-frames]] | `VideoFrameAnalyzer` | video | ml | high | Sample frames -> ensemble |
| 06 | [[analyzers/audio-spectrogram]] | `AudioAnalyzer` | audio | default | mid | Spectral artifact check |
| 07 | [[analyzers/llm-text]] | `LLMTextAnalyzer` | text | ml | mid | AI authorship classifier |

> [!gap] Multi-modal video
> Video MIME currently routes ONLY to [[analyzers/video-frames]]. Audio track is NOT extracted -> [[analyzers/audio-spectrogram]] skipped. Metadata also skipped. Gap to close later.

## Dispatch

`analyzers/tasks.py:dispatch_analysis` builds a Celery `chord(group(run_analyzer for each config))` -> `aggregate_verdicts` callback. See [[concepts/submission-pipeline]].

Each `run_analyzer` task:

1. Loads class via `analyzers/registry.py:load_analyzer_class`
2. MIME guard
3. Updates `submission.status_message`
4. Pulls file from MinIO (`storage_utils.local_file`)
5. Calls `analyzer.analyze(...)`
6. Creates [[models/AnalysisResult]] row
7. Excepts -> creates row with verdict=error

## Source files

`backend/analyzers/implementations/`:
- `metadata_analyzer.py`
- `ela_analyzer.py`
- `clip_detector.py` (AI ensemble; legacy class name from earlier CLIP experiments)
- `llm_image_analyzer.py`
- `video_analyzer.py`
- `audio_analyzer.py`
- `llm_analyzer.py` (text)
