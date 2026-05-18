---
type: research-synthesis
created: 2026-05-14
updated: 2026-05-18
status: week-1-in-progress
---

# 2026 Detection Strategy (rebuild plan)

Research synthesis by user 2026-05-14. Current Qwen-as-oracle pipeline is structurally wrong. Plan: demote VLM to describer/explainer, put purpose-trained binary classifiers behind a calibrated ensemble.

## Why current pipeline fails

VLMs (Qwen, GPT-4V, Gemini, Claude-3) score ~48% AUC on deepfake benchmarks (arXiv 2503.14853) - **worse than coin flip**. Not a prompting bug: instruction tuning strips discriminative signal from vision encoder (Zhang et al. arXiv 2405.18415; Co-Spy CVPR 2025). Tokenization at 224-384px destroys upsampling traces, DCT residuals, CFA/PRNU noise, JPEG quantization tables, latent-prior bias - the signals that actually separate synthetic from real.

Honest accuracy reality:

| Setting | Achievable accuracy |
|---------|---------------------|
| Same-generator (train SD1.4 -> test SD1.4) | 98-100% |
| Architectural sibling | 95-99% |
| Cross-family (SD -> MJ v5) | 54-70% |
| Modern commercial (any -> Flux/Firefly v4/MJ v7) | 18-30% mean |
| In-the-wild "Chameleon" curated | ~55-65% |
| Best single zero-shot generalist (Community-Forensics) | 75% mean |

NPR-trained detectors collapse to 18-31% on Flux/Firefly v4/Imagen 4 (arXiv 2602.07814, 23 detectors x 12 datasets x 291 generators).

**Realistic capstone target: 75-85% AUC on in-the-wild content with calibrated ensemble.**

## New role for Ollama / Qwen

Keep, demote to tail of pipeline. Run AFTER calibrated ensemble produces verdict + evidence dict. Prompt:

> "Given this evidence (sub-scores, ELA heatmaps, pHash matches, fact-check results, OCR'd text), write 2-paragraph explanation citing specific signals."

Genuine VLM strengths:
- Content captioning
- OCR (especially garbled AI text on Midjourney/Flux/Sora)
- Counting/anatomy ("six fingers, asymmetric earrings")
- Translation
- Claim extraction from extracted text
- Human-readable explanation over numeric output

Replace Moonlight (no signal). Use Qwen2-VL-7B Q4_K_M or MiniCPM-V 2.6 (8B). MiniCPM-V has better OCR per VRAM dollar.

## Image detection - priority integration order

### 1. NPR (Neighboring Pixel Relationships) - CPU, 100ms/image
Repo: `github.com/chuangchuangtan/NPR-DeepfakeDetection`. ResNet-50 (~90M params), trained on ProGAN, generalizes 93.3% mean across 28 generators incl. 11 diffusion families via universal upsampling fingerprint. Weakens on Flux/MJ v7 (DiT, no upsampling trace) but cheapest strong signal. **Apache-2.0**.

### 2. UniversalFakeDetect - 1.5MB linear probe on frozen CLIP
Repo: `github.com/WisconsinAIVision/UniversalFakeDetect`. CVPR 2023. Linear head on CLIP ViT-L/14. **Differentiation lives here:** fine-tune on a few thousand of YOUR OWN labeled images in 10 min on Colab T4. Frozen CLIP avoids training-set bias trap.

Extensions: CLIPping the Deception (arXiv 2402.12927), GenD (arXiv 2508.06248) - LayerNorm-only tuning, slightly better.

### 3. AIDE OR Community-Forensics - modern generators workhorse
- AIDE (`github.com/shilinyan99/AIDE`, ICLR 2025): 86.88% mean on GenImage. Best published OOD generalizer. ~700M MoE - wants GPU.
- Community-Forensics (`OwensLab/CommunityForensics-Small` on HF, NeurIPS 2024): trained on 2.7M images from 4,803 generators. **75% mean across 12 datasets** - strongest single zero-shot generalist. Solves the right problem (training diversity > architecture).

### Avoid
- `Organika/sdxl-detector` - **cc-by-nc-3.0**, cannot ship in paid SaaS. (Also broken weights, already removed.)
- `umm-maybe/AI-image-detector` - VQGAN era, obsolete on Flux/MJ/SDXL.
- DIRE - runs full diffusion at inference (5-15s/image), not viable.

### Apache-2.0 substitute
`prithivMLmods/deepfake-detector-model-v1` - SigLIP-base, ~94% on author's eval, Apache-2.0.

## Ensemble + calibration

Reference: DeepSafe (`github.com/siddharthksah/DeepSafe`) - already wires NPR + UniversalFakeDetect + CrossEfficientViT through average/voting/stacking.

Recipe:

```python
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

# 1. Each detector: raw p_fake
# 2. Per-detector isotonic calibration on 1000 held-out labels:
calibrator = CalibratedClassifierCV(method="isotonic")
calibrator.fit(detector_scores, labels)
# 3. Meta-learner combines calibrated probs:
meta = LogisticRegression()  # +2-4% over weighted average
# 4. Temperature scaling for NN logits if available
# 5. Conformal intervals: mapie library
```

## Disagreement handling

When detectors disagree by `> 0.4`, set verdict to **uncertain** + surface conflict:

> "ELA flags localized manipulation; CLIP-based generator detection scores low - recommend manual review."

Store every sub-score. Honest + differentiator vs "99% accuracy" snake oil.

This matches current `needs_review` rule but tighter threshold and explicit conflict explanation. See [[concepts/aggregation]].

## Text detection

GPT-4o / Claude 3.5+ / Gemini 2 detection at paragraph length **under paraphrase is not solved**. RAID benchmark (ACL 2024): commercial detectors claiming 99% collapse to 30-60% on diverse prompts. Stanford (Liang et al. arXiv 2304.02819): 7 commercial detectors misclassify TOEFL ESL essays as AI **61.3%** of the time vs 3.2% on US 8th-grade - critical at DMU Kazakhstan.

### Primary: Binoculars
arXiv 2401.12070, `github.com/ahans30/Binoculars`. Cross-entropy ratio between two Falcon-7B models (observer vs performer). >90% TPR at 0.01% FPR on ChatGPT. **99.67% on ESL TOEFL** - only detector trustworthy around non-native English. Cost: ~16GB VRAM in fp16.

### Pair: desklib/ai-text-detector-v1.01
DeBERTa-v3-large, ~1.7GB, CPU-runnable, Apache-2.0. Currently #1 on RAID.

### For Russian (Kazakhstan relevance)
Fine-tune mDeBERTa-v3-base on M4 multilingual + RuATD. Expect 80-90% in-domain.

### Kazakh
No off-the-shelf detector. Label small dataset and fine-tune mDeBERTa, OR mark Kazakh "explicitly unsupported" in UI.

### Avoid
- Ghostbuster - authors warn against ESL, contraindicated.
- `openai-community/roberta-base-openai-detector` - GPT-2 era, obsolete.
- Hello-SimpleAI - HC3 Q&A only, poor cross-domain.
- Fast-DetectGPT - expensive (6B+2.7B model pair).

### Watermarks
- OpenAI text watermark - **never shipped** (WSJ Aug 2024).
- Google SynthID-Text - in HF Transformers v4.46+, Gemini outputs ONLY. Free positive signal when present.

## Audio detection

ASVspoof-trained models **don't generalize** to ElevenLabs / OpenAI TTS / PlayHT (neural codec / diffusion synthesis, different from HiFiGAN/MelGAN). CodecFake paper documents collapse. ReplayDF: top models 4.7% -> 18.2% EER under replay.

### Start: AASIST-L
`github.com/clovaai/aasist`. 85K params, ms-range CPU. Fine-tune on:
- ASVspoof 2019/21
- MLAAD (multi-language, Bark/Tortoise/XTTS/Coqui)
- CodecFake
- **Generate your own** few hundred ElevenLabs/OpenAI TTS samples (use free tier)

### Heavy backup (GPU)
`nii-yamagishilab/xls-r-2b-anti-deepfake` - XLS-R-2B trained on 74k+ hrs. Strongest single open detector. Audit Resemble's DETECT-3B Omni (partially open) too.

**Generate your own evaluation set before claiming accuracy.** Vendor-trained detectors lie about generalization routinely.

## Video detection

Face manipulation: mature. GenConViT (`github.com/erprogs/GenConViT`, 695M params): 95.8% acc / 99.3% AUC on FF++/DFDC/Celeb-DF v2. Run only on face-bearing frames after face detection.

Full AI-video (Sora 2 / Veo 3 / Kling 2.5 / Runway Gen-4): **no robust open-source solution May 2026**. AIGVDBench (arXiv 2601.11035, 31 generators / 440k videos / 33 detectors): research-stage only.

For v1: sample frames every N seconds, run image ensemble, add temporal-consistency via DINOv2 frame embeddings + change-point statistics. UI label: "AI-video detection unreliable for current-generation video models".

Commercial fallback if customer demands: Sightengine, Hive - wrap behind Analyzer interface.

## Classical forensics

Reframe: ELA, PRNU, JPEG ghosts, CFA were designed for splicing/manipulation forensics on JPEGs from physical cameras. Answer "edited after capture?" not "born from diffusion?". Krawetz (ELA inventor) explicitly warns ELA cannot solely declare an image doctored - high FP on textured regions.

Make them **human-analyst inspector view**, not auto-verdict. Celery tasks produce artifact PNGs into MinIO:
- ELA
- JPEG ghost
- Double-JPEG
- Copy-move (block + keypoint)
- Noiseprint (CNN-learned camera fingerprint, practical successor to PRNU for AI detection)

Reference codebase: Sherloq (`github.com/GuidoBartoli/sherloq`, MIT/GPL). Reuse algorithms, not GUI. `jpegio` for DCT coefficient access.

**PRNU NOT viable for SaaS** - needs 50+ flat-field reference images per device. Recent 2024 work: PRNU forgeable at 85.5% success against tools like Amped Authenticate.

### Metadata wins
A surprising fraction of naive AI uploads detectable from metadata alone:
- pyexiftool wrapper around exiftool
- Software tag: "Stable Diffusion / Midjourney / DALL-E / Firefly / Gemini"
- PNG tEXt/iTXt chunks (SD writes `parameters` by default with full prompt)
- JUMBF box presence
- Quantisation-table fingerprints

## Provenance - your strongest signal

### C2PA Content Credentials
Adoption picture May 2026:
- Leica M11-P, SL3-S - sign by default
- Sony a1/a1II/a9III/a7 - via Creators' App
- Canon EOS R1/R5II/R5C/C70 - rolling out
- Google Pixel 10 - signs all photos (Tensor G5 + Titan M2)
- Samsung S25 - signs AI-edited only
- OpenAI DALL-E 3 / GPT-Image - add manifests
- Adobe Firefly/Photoshop/Lightroom - mature

Nikon Z6III service suspended 2025 (signing-key vuln) - **manifests forgeable when keys leak**.

Integrate: `c2pa-python` v0.32.x (bindings to Rust c2pa-rs). Validate via `Reader.validation_state()` -> `valid` / `invalid` / `untrusted`.

Display "provably real per C2PA" as **strongest positive signal**. Stripped/unsigned = absence-of-positive, NOT a fake verdict.

### Perceptual hashing into pgvector
Highest-ROI feature. Compute three hashes per image:
- 64-bit pHash (`imagehash` pip)
- 256-bit PDQ (`pdqhash`, Facebook production-tested, rotation/flip variants, quality score)
- 768-d CLIP ViT-L/14 embedding (semantic near-dup)

Store in pgvector 0.7+ with HNSW indexing:
- `bit(64)` with `hamming_distance` for pHash
- `bit(256)` with `bit_hamming_ops` for PDQ
- `vector(768)` with `vector_cosine_ops` for CLIP

Graduated thresholds:
1. Exact SHA-256 match
2. pHash distance <= 4
3. PDQ distance <= 32
4. CLIP cosine >= 0.92

Postgres becomes similarity-search engine. No second datastore until ~50M images.

**Skip NeuralHash** - adversarially broken (Struppek et al. FAccT 2022). PhotoDNA restricted to NCMEC/NGOs.

### Reverse image search
- TinEye Commercial - only one with crawl timestamps for "first seen" provenance. Starter $200/mo for 5k searches @ $0.04/each.
- Google Cloud Vision WEB_DETECTION - $1.50/1k, cheaper for matching pages, no reliable timestamp.
- **Bing Web Search API retired Aug 11, 2025** - don't build on it.
- Build internal reverse-search: index CLIP embeddings of scraped news photos in pgvector. Complements TinEye.

## Fact-checking pipeline

Reference: Loki / OpenFactVerification (`github.com/Libr-AI/OpenFactVerification`, MIT, MBZUAI + Monash). 5 stages map onto Celery chord:

1. Decomposer
2. Checkworthiness Identifier
3. Query Generator
4. Evidence Retriever (Serper)
5. Claim Verifier

### Claim extraction
**Claimify** (Microsoft, arXiv 2502.10855): Selection -> Disambiguation -> Decomposition. 99% entailment / 87.6% coverage / 96.7% precision. SOTA.

`BharathxD/ClaimeAI` on GitHub has LangGraph implementation - port to Celery.

Extract via local Qwen2.5-32B (Ollama, free). Synthesize verdicts via GPT-4o-mini or Claude Haiku where quality matters.

### Search APIs (2025-2026 landscape shifted)
- **Bing Web Search retired Aug 2025**
- **Tavily acquired by Nebius Feb 2026** (roadmap uncertain)
- **Brave Search API** moved to $5/mo credit model Feb 2026
- **Google sued SerpAPI Dec 2025** (ongoing)

Behind abstraction layer. Recommended trio:
- **Google Fact Check Tools API** (free) - hits ClaimReview-marked verdicts from Snopes/PolitiFact/AFP. Highest-precision first lookup.
- **Serper.dev** ($0.30-1.00 per 1k queries) - cheapest reliable Google SERP proxy. 2,500/mo free.
- **Exa** ($0.001/result) - semantic search for multi-hop when keyword fails.

Add Firecrawl or Jina Reader for full-text extraction when snippets insufficient.

Realistic cost: 1000-word article -> 15-30 atomic claims -> $0.15-1.50 uncached, $0.03-0.30 with aggressive Redis cache.

### Source credibility (MVP)
NewsGuard gold standard but $10k+/year. Scrape MBFC from public datasets (`idiap/Factual-Reporting-and-Political-Bias-Web-Interactions`), cross-ref Wikipedia Reliable Sources Perennial List. Manual override table. Compose `domain -> {credibility 0-1, bias -3..+3, source}` cached daily.

**Honest accuracy ceiling for MVP fact-checker: 75-85% verdict precision.** Originality.ai: 83.5% recall. AVeriTeC top: 0.50 official metric. FEVER baseline with correct evidence: 31.87%.

**Human-in-the-loop mandatory for high-stakes claims.**

## Architecture changes

### Hybrid serving
- **Light analyzers** (pHash, EXIF, ELA, meta-learner, regex) inside Celery prefork workers
- **Heavy ML** (CLIP detector, AASIST, Whisper if needed) in **single FastAPI/BentoML inference container** that holds models in memory once. Workers HTTP into it.
- Ollama stays separate for VLM tasks.

This avoids the Pattern-A trap: each prefork child reloading 1.5GB PyTorch -> OOM at 4 workers.

### Celery config
- `worker_max_tasks_per_child=100`
- `worker_max_memory_per_child=2_000_000`
- `worker_prefetch_multiplier=1`
- `task_acks_late=True`

### Queue routing
- `cpu_fast` queue: prefork pool `-c 4` for cheap stuff
- `gpu` queue: `--pool=solo -c 1` - exactly one model in VRAM
- `vlm` queue: solo too

### Chord pattern
```python
def analyze(content_id, modality):
    analyzers = AnalyzerRegistry.for_modality(modality)
    header = [a.signature(content_id) for a in analyzers]
    return chord(header)(aggregate.s(content_id=content_id))
```

Attach `link_error` on each header subtask. Aggregator gracefully handles missing/errored (treat as "no signal"). Never fail whole analysis on one detector exception.

### Pluggable analyzer design
- ABC + class-decorator registry + dataclass result schema
- ONE Django app `analyzers/` with subpackage per analyzer (NOT one app per - pollutes INSTALLED_APPS + migrations)
- `AnalyzerResult` dataclass: `analyzer_id, modality, score (calibrated [0,1]), raw_score, verdict, confidence, explanation, evidence (dict), latency_ms, model_version, error`
- `AnalyzerConfig` Django model lets admins toggle at runtime per modality (already have this)

### Lazy model loading
`PredictTask` base class - `celery.Task` subclass with `@property model` that loads on first access. Pair with `worker_process_init` signal to load before fork.

### Real-time progress
Django Channels + WebSockets (Redis is already channel layer). `celery-progress` library has drop-in WebSocket support. **Avoid SSE** - clashes with WSGI worker timeouts. **Avoid polling** - wastes Redis ops.

### Caching
Key: `sha256(file_bytes) + ":" + analyzer_id + ":" + model_version`. Two-tier TTL:
- Per-analyzer partial: 30 days (immutable until model bumps)
- Final aggregated: 7 days

Bump `model_version` in code -> auto-invalidate.

## Deployment

Student budget: **$15-40/month total**.

### Tier 1: $10-15/mo Hetzner CX32 or Contabo VPS L
4 vCPU, 8-16GB RAM. Runs Django + Postgres + Redis + MinIO (or Cloudflare R2 free tier) + Celery cpu_fast + small Ollama VLM on CPU.

### Tier 2: RunPod Serverless (per-second billing)
RTX 4090 ~$0.34/hr equivalent. Idle = $0. Hosts FastAPI inference container. Typical capstone demo: $0-30/mo. Modal alternative: $30/mo free credit.

**Avoid hyperscalers** (AWS/GCP at $3-4/hr A100). Burns budget in days.

### Cheaper single-VPS fallback
$15 VPS. NPR + UniversalFakeDetect on CPU at 1-3s/image (async OK). MiniCPM-V Q4 CPU for explanation at 10-30s. Skip GPU.

GitHub Student Pack: $200 DigitalOcean credit. GCP $300 free for new accounts.

## Week-by-week roadmap

| Week | Focus |
|------|-------|
| 1-2 | Provenance + cheap wins: pHash + PDQ + CLIP into pgvector with HNSW. EXIF/IPTC/XMP with pyexiftool. C2PA with c2pa-python. Seed known-fakes from public datasets (GenImage, ArtiFact, WildFake, MIT Detect Fakes). |
| 3-4 | Image detection: NPR on CPU. UniversalFakeDetect (CLIP linear probe) + fine-tune on few thousand of your own labels covering MJ v6, Flux dev, SDXL, DALL-E 3 vs real Unsplash. Replace Qwen call with these two. Add ELA as third complementary signal. |
| 5 | Text detection: desklib/ai-text-detector-v1.01 (CPU). Binoculars only if GPU. Google Fact Check Tools API via Claimify prompts in Ollama. |
| 6 | Audio: AASIST-L fine-tuned on ASVspoof 2019/21 + MLAAD + CodecFake + your own ElevenLabs/OpenAI samples. CPU. |
| 7 | Video + ensemble: Frame-sample with image ensemble. Defer GenConViT until GPU. Build meta-learner: 500-2000 labeled validation set (FF++ + Celeb-DF + 200 in-the-wild). Per-detector isotonic calibration. Logistic stacker. |
| 8 | Fact-check + polish: Claimify extraction -> Google FC -> Serper.dev -> Exa -> NLI ranking (MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli) -> Qwen verdict synthesis. Channels WebSocket progress. |

## Product positioning shift

**ProofLayer is not an AI detector. It's a multi-signal provenance and corroboration platform.**

Maps onto three pillars:
1. ML detection (calibrated ensemble)
2. Fact-checking (Claimify + Google FC + Serper + Exa)
3. Provenance database (C2PA + pHash + reverse search + known-fakes)

Every result: confidence interval + evidence breakdown, NOT a binary verdict. Aligns with Reality Defender, Hive, Sensity self-description: "ensemble of models" with explainable heatmaps.

## Cross-refs

- [[analyzers/_index]] - current analyzers (to be replaced)
- [[analyzers/llm-vision]] - Qwen will move to tail
- [[concepts/aggregation]] - calibration upgrade target
- [[concepts/memory-budget]] - hybrid serving solves the OOM problem
- [[infrastructure/memory-limits]]
- [[fixes/organika-broken]] - license + obsolescence
