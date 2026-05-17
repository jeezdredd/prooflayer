---
type: model
created: 2026-05-14
source: backend/analyzers/models.py
table: analysis_results
---

# AnalysisResult

One row per analyzer per submission. Stores raw evidence + verdict + confidence.

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `submission` | FK -> [[models/Submission]] | CASCADE |
| `analyzer` | FK -> [[models/AnalyzerConfig]] | PROTECT |
| `confidence` | Float | 0..1, analyzer-internal |
| `verdict` | enum | `authentic` / `suspicious` / `fake` / `inconclusive` / `error` |
| `evidence` | JSONField | per-analyzer schema |
| `execution_time` | Float nullable | seconds |
| `error_message` | TextField | populated on `verdict=error` |
| `created_at` | DateTime | auto |

Unique constraint: `(submission, analyzer)` -> one result per analyzer per submission.

## Evidence shapes (per analyzer)

- [[analyzers/metadata]] -> `{metadata_presence, ai_tool, dates, gps, flags}`
- [[analyzers/ela]] -> `{mean_error, std_error, uniformity_ratio, source_format, ...}`
- [[analyzers/ai-ensemble]] -> `{classifiers[], ai_probability_avg, ai_probability_max, ensemble_size, content_check}`
- [[analyzers/llm-vision]] -> `{llm_verdict, reasoning}`
- [[analyzers/video-frames]] -> `{frame_results[], ai_frame_ratio, frames_analyzed}`
- [[analyzers/audio-spectrogram]] -> `{spectral_*, mfcc_*, ...}`
- [[analyzers/llm-text]] -> `{llm_verdict, reasoning}`

## Aggregation input

Consumed by [[concepts/aggregation]] via `aggregate(results)` -> `(final_score, final_verdict)`.

## See also

- [[analyzers/_index]]
- [[concepts/aggregation]]
- [[concepts/verdict-thresholds]]
