# Report corrections

Cross-checked report claims against live codebase. Fix these before submission.

---

## Must fix

### 1. Vision model - wrong model throughout

**Claimed:** Qwen2.5-VL 3B
**Actual:** `llava:7b` (`backend/config/settings/base.py:157` - `OLLAMA_VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "llava:7b")`)

Affects: abstract, sections 2.3, 5.4, 6.2, 8.2, and the OOM/latency narrative (4 GB resident, 18 s CPU pass was written for Qwen - re-measure or remove specific figures).

Replace all "Qwen2.5-VL 3B" with "LLaVA 7B".

---

### 2. SigLIP detector does not use SigLIP

**Claimed:** "SigLIP-base binary classifier (Apache-2.0)"
**Actual:** `prithivMLmods/Deep-Fake-Detector-v2-Model` - a ViT classifier (`backend/analyzers/implementations/siglip_detector.py:12`)

Affects: abstract, section 6.2.

Replace "SigLIP-base binary classifier" with "ViT binary classifier (prithivMLmods/Deep-Fake-Detector-v2-Model)".

---

### 3. Access token TTL

**Claimed:** 15 minutes (section 6.1, two occurrences)
**Actual:** 30 minutes (`backend/config/settings/base.py:127` - `timedelta(minutes=30)`)

Replace both "15 minutes" with "30 minutes" in section 6.1.

---

### 4. KnownFakeHash entry count

**Claimed:** "around thirty entries cited from Reuters Fact Check, BBC Verify, Snopes, PolitiFact, AFP" (sections 5.3 and 6.4)
**Actual:** 8 entries in seed (`backend/content/management/commands/seed_known_fakes.py`)

Options:
- Change "around thirty" to "eight" everywhere
- Expand the seed to ~30 entries before defense (sources already cited are fine, just the count is wrong)

---

## Fix before submission

### 5. Frontend library versions (section 5.6)

| Claim | Actual | Source |
|-------|--------|--------|
| React Router v6 | **v7** (`^7.1.0`) | `frontend/package.json` |
| Tailwind v4 | **v3** (`^3.4.0`) | `frontend/package.json` |

---

### 6. Container count (section 5.1)

**Claimed:** "seven containers"
**Actual:** 10 services in `deploy/compose.prod.yml`:

| Service | Type |
|---------|------|
| `db` | long-running |
| `redis` | long-running |
| `backend` | long-running |
| `celery_worker` | long-running (beat embedded) |
| `flower` | long-running |
| `minio` | long-running |
| `ollama` | long-running |
| `frontend` | long-running |
| `minio_init` | init one-shot |
| `ollama_init` | init one-shot |

Change "seven containers" to "eight long-running containers plus two init helpers". Add Flower to the list in section 5.1 (it is mentioned in 3.3 and 7.2 but not counted).

---

## Optional additions (strengthen, not correct)

### 7. CLIP embeddings + PDQ - missing from provenance description (sections 5.5, 6.4)

`content/models.py` has `clip_embedding` (pgvector 512-dim, HNSW index), `pdq_hash`, `pdq_quality` on the Submission model. The report mentions pgvector once (section 5.1) but never explains what is indexed. Add to section 6.4:

> "Near-duplicate semantic search uses CLIP ViT-B/32 embeddings indexed via pgvector with an HNSW index, alongside pHash, dHash, and Facebook PDQ hashes."

This explains why pgvector is in the stack and adds a concrete technical detail.

---

### 8. Provenance timing (section 5.3)

Report implies provenance runs after aggregation. Code runs the perceptual known-fake check and provenance scan before the analyzer chord is dispatched (`backend/content/tasks.py:105-117`). Minor - safe to leave for readability, but useful to know for viva Q&A.

---

### 9. Chord lives in analyzers app, not content (section 5.3)

Report says `process_submission` dispatches a group/chord. The group+chord is actually built in `backend/analyzers/tasks.py:58-59`, called via `dispatch_analysis.delay()`. Minor - safe to leave, but know the actual file if asked.

---

## What is accurate

- All 9 analyzer names and weights match seed exactly
- Aggregator logic: CF threshold 0.92, peer requirement, score floor 0.85, disagreement gate (2v2), single-voter downgrade - all correct
- 6 verdict strings (5 from `_band`, `needs_review` from disagreement gate) - correct
- Auth cookie: name, httpOnly, SameSite=Lax, path, 7d TTL - all correct
- token_blacklist with BLACKLIST_AFTER_ROTATION=True - correct
- EmailVerificationToken: token_urlsafe(32), 48h expiry - correct
- IsVerifiedUser permission class - correct
- 8 local Django apps - correct
- 3 Celery queues (default, ml, reports) - correct
- Weekly retrain: Sunday 03:00, min 50 samples - correct
- FactCheck: spaCy NER + qwen2.5:3b + Google Fact Check API + DuckDuckGo context - correct
- npr_detector: `Wvolf/ViT_Deepfake_Detection` - correct
- community_forensics: `buildborderless/CommunityForensics-DeepfakeDet-ViT` - correct
- All major model fields (Submission, AnalysisResult, AnalyzerConfig, VerdictOverride, RetrainRun, Vote, KnownFakeHash) - correct
