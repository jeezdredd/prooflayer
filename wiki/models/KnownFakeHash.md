---
type: model
created: 2026-05-14
source: backend/content/models.py
table: known_fake_hashes
---

# KnownFakeHash

Seed list of SHA-256 digests known to be fake/synthetic. Used for fast denylist short-circuit on upload.

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `sha256_hash` | CharField(64) unique | indexed |
| `source` | CharField(255) | origin label e.g. "internal", "imageforensic.org" |
| `description` | TextField | optional context |
| `added_at` | DateTime | auto |

## Usage

`content/services.py:create_submission` checks new upload's sha256 against this table. If hit -> `submission.is_known_fake = True` (still runs full pipeline for evidence). [[frontend/routes|Dashboard]] visually flags such rows.

## Seeding

`backend/content/management/commands/seed_known_fakes.py` populates from a CSV / curated source.

## See also

- [[models/Submission]]
