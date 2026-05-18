---
type: concept
created: 2026-05-18
status: week-1
source: backend/content/services.py, backend/provenance/services.py
---

# Perceptual Provenance Stack (Week 1)

Cheap signals computed at upload time before heavy analyzers fire. Goal: catch the easy cases (exact / near-duplicate of known fakes, semantic neighbours of past verdicts, C2PA-signed originals) for ~0 compute cost.

## Hashes computed

Per upload, in `compute_perceptual_hashes()` (`backend/content/services.py`):

| Hash | Lib | Output | Use |
|------|-----|--------|-----|
| SHA-256 | hashlib | 64 hex | exact-match cache + known fakes |
| pHash | imagehash | int64 (signed) | hamming dist <= 6 -> near-duplicate |
| dHash | imagehash | int64 | secondary perceptual signal |
| PDQ | pdqhash (Meta) | 256-bit hex + quality 0-100 | rotation/flip-tolerant, Facebook prod-tested |
| CLIP ViT-B/32 | transformers | 512-d normalized vector | semantic similarity via pgvector cosine |

CLIP base-patch32 chosen over Large (1.7 GB) for CPU latency: ~580 MB, 50 ms / image. Lazy-loaded module-level singleton (`_CLIP_STATE`).

## Storage

`Submission` columns (`backend/content/models.py`):
- `phash`, `dhash`: `BigIntegerField` (signed)
- `pdq_hash`: `CharField(64)` hex, `pdq_quality`: smallint
- `clip_embedding`: `pgvector.django.VectorField(dimensions=512)`

HNSW index on `clip_embedding` (`vector_cosine_ops`, m=16, ef=64) -> sub-ms nearest-neighbour over millions of rows.

`KnownFakeHash` extended with same perceptual columns -> seed table doubles as Hamming target.

## Matchers (`backend/provenance/services.py`)

- `check_perceptual_known_fake(submission)`: raw SQL `bit_count((phash # known.phash)::bit(64)) <= 6`. If any KnownFakeHash with phash within Hamming 6, mark `is_known_fake=True`. Catches re-uploads with crop/recompress.
- `find_clip_neighbors(submission, max_distance=0.15)`: pgvector `CosineDistance` HNSW query. Returns top-5 semantic neighbours from prior submissions. Stored as `ProvenanceResult` rows with `method=clip_cosine`.
- `extract_c2pa(submission)`: optional `c2pa-python` import. Reads manifest bytes from file. If present, stored as `ProvenanceResult(source_type=C2PA)`.
- `scan_provenance(submission)`: pipeline entrypoint. Runs all three in sequence. Wired into `content/tasks.process_submission` after hash compute, before analyzer dispatch.

## Pipeline order

```
upload -> save file -> compute SHA -> SHA cache hit? -> return cached
                    -> compute_perceptual_hashes (phash, dhash, pdq, clip)
                    -> check_perceptual_known_fake (Hamming match)
                    -> scan_provenance (phash neighbours, clip neighbours, c2pa)
                    -> dispatch_analysis (heavy ML)
```

## Thresholds (tunable)

```python
PHASH_KNOWN_FAKE_THRESHOLD = 6     # Hamming 0-6 = match
CLIP_COSINE_DISTANCE_MAX   = 0.15  # 1 - cosine_sim; ~0.85 sim
CLIP_NEAREST_LIMIT         = 5
```

Conservative defaults. Raise CLIP threshold if too noisy, lower if missing dupes.

## Dependencies

```toml
pgvector>=0.3,<1.0
pdqhash>=0.2,<1.0
# optional:
c2pa-python>=0.6,<1.0
```

`pgvector.django` added to `INSTALLED_APPS`. Postgres extension created via `migrations/0007_pgvector_extension.py` (`VectorExtension()` op).

## Verification

Local sanity:
```bash
DJANGO_SETTINGS_MODULE=config.settings.dev uv run python -c "
import django, sys; sys.path.insert(0, 'backend'); django.setup()
from content.services import compute_perceptual_hashes
print(compute_perceptual_hashes('/path/to/test.jpg'))
"
```

End-to-end: upload duplicate of an existing submission -> `ProvenanceResult` rows with phash distance 0-2 + CLIP distance ~0.02. Upload semantic sibling (same scene, different framing) -> CLIP distance 0.05-0.12, no phash match.

## See also

- [[detection-strategy-2026]] - 8-week parent plan
- [[models/Submission]] - schema
- [[models/KnownFakeHash]] - seed table
- [[services/postgres]] - pgvector extension
