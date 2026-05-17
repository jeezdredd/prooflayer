---
type: model
created: 2026-05-14
source: backend/content/models.py
table: submissions
---

# Submission

Core unit of work. One row per uploaded file.

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK, default uuid4 |
| `user` | FK -> User | CASCADE, `related_name="submissions"` |
| `original_filename` | CharField(255) | as uploaded |
| `file` | FileField | `submissions/%Y/%m/%d/` |
| `thumbnail` | ImageField | `thumbnails/%Y/%m/%d/`, optional |
| `mime_type` | CharField(100) | sniffed |
| `file_size` | PositiveInt | bytes |
| `sha256_hash` | CharField(64) | indexed, dedup + known-fake check |
| `status` | enum | `pending` / `processing` / `completed` / `failed` |
| `metadata` | JSONField | raw inspection blob |
| `status_message` | CharField(100) | live message during processing |
| `final_score` | Float nullable | 0..1, from [[concepts/aggregation]] |
| `final_verdict` | CharField(30) | label from [[concepts/verdict-thresholds]] |
| `is_known_fake` | Boolean | matched [[models/KnownFakeHash]] |
| `phash` | BigInt nullable | perceptual hash, indexed |
| `dhash` | BigInt nullable | difference hash, indexed |
| `approved_for_training` | Boolean | crowdsource curated label |
| `verified_label` | enum | `real` / `fake` (manual) |
| `created_at` | DateTime | auto |
| `updated_at` | DateTime | auto |

Default ordering `-created_at`.

## Status state machine

```
pending → processing → completed
                    └→ failed
```

Transitions in `analyzers/tasks.py`:
- `pending` -> `processing` on first analyzer message
- `processing` -> `completed` after `aggregate_verdicts`
- `processing` -> `failed` on chord failure

## Related

- `submission.analysis_results` -> [[models/AnalysisResult]] (1:N)
- `submission.verdict_overrides` -> [[models/VerdictOverride]] (1:N)
- crowdsource votes (separate app)

## Computed in services

`content/services.py:create_submission` + `compute_hashes` populate:
- `sha256_hash` (file content digest)
- `phash`, `dhash` (image perceptual; via `imagehash` lib)
- `thumbnail` (Pillow resize for images, ffmpeg frame for video)
- `mime_type` (from upload header + magic byte sniff)

`find_similar_submissions(submission)` queries other rows by `phash` Hamming distance for similarity panel on result page.

## See also

- [[concepts/submission-pipeline]]
- [[models/AnalysisResult]]
- [[models/VerdictOverride]]
