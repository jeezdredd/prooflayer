---
type: concept
created: 2026-09-04
source: backend/analyzers/ensemble.py
aliases: [Tribunal, ensemble, Кооператив]
---

# Tribunal

The name of the detector ensemble as a whole: the seeded analyzer roster, their weights, the
aggregation rules ([[concepts/aggregation]]) and any per-detector calibration. A tribunal in the
literal sense - a panel of judges with unequal standing, each weighing the same evidence, a
weighted vote that returns a *verdict*, and a rule for when the bench is split enough that the
case goes to a human (`needs_review`). The rest of the codebase already speaks this language:
`verdict`, `evidence`, corroboration, override, review queue.

Working name was "Кооператив" for about an hour on 2026-09-04; the constant is one line in
`analyzers/ensemble.py` if it changes again. Runners-up: Quorum (after
`MIN_CORROBORATING_FOR_FAKE`), Argus (many eyes), Consilium.

Code: `analyzers/ensemble.py` - `ENSEMBLE_NAME`, `ENSEMBLE_VERSION`, `ensemble_info()`.

## Where it shows

- `GET /api/v1/submissions/<id>/` -> `ensemble: {name, version, label, fingerprint}` on every
  detail response, so a stored verdict can be traced to the configuration that produced it.
- `GET /api/v1/system/status/` -> `services.analyzers.ensemble` = `"Tribunal 1.2"` next to the
  roster-drift probe ([[api/system-status]]).
- `manage.py eval_detectors` prints the label and fingerprint in its header.

## Versioning

Since 2026-10-13 every submission is **stamped** at aggregation time with `tribunal_version` and
`tribunal_fingerprint`. The detail response returns that stamp (not the live Tribunal) plus
`current_version` and `is_current`; the result page shows "verdict by Tribunal 1.1 / current 1.3"
and a **Re-analyze** button when the stamp is stale (`POST /content/submissions/<id>/reanalyze/`,
owner or staff, counts against the monthly quota). Submissions judged before the stamp existed
return `ensemble: null`.


- `version` is bumped by hand when the tribunal's *behaviour* changes: membership, weights,
  aggregation rules, calibration, a retrained member. Bug fixes that do not change verdicts on
  the eval sets do not bump it.
- `fingerprint` is a 12-hex sha256 over `name:class:weight` of the seeded roster, order
  independent. It changes on every roster edit whether or not `version` was bumped, which is
  the safety net: two verdicts with different fingerprints were produced by different
  tribunals even if both say 1.0.
- A version is only declared after it has been measured with `eval_detectors` on both
  `dataset/hf` (2022 diffusiondb) and `dataset/openfake` (20 current generators). The numbers
  go in the changelog below, not in prose elsewhere.

## Phase F result (2026-10-13): not shipped

Retrained custom_detector (CF backbone, 1/3/5 epochs) on openfake + hf + openfake_big (1400 more
images, 1 duplicate removed, none overlapping openfake_test) plus a retrained CLIP probe. Measured
through the real aggregate() on openfake_test (245) and a separate calibration pool:

| config | openfake_test caught /145 | AI->authentic | real->fake | calib pool caught /149 |
|---|---|---|---|---|
| 1.3 shipped (custom 3.5 / probe 2.5) | 108 | 6 | 0 | 127 |
| 1.3 models, probe weight 3.5 | 111 | 5 | 0 | 127 |
| candidate e3 + new probe, best weights | 105 to 108 | 6 to 7 | 0 | 124 to 125 |

More data of the same kind did not help, and the probe-weight gain on openfake_test did not
reproduce on the calibration pool (fit-on-test optimism). Decision: keep 1.3 for images. The
candidate stays in ~/.cache/huggingface/prooflayer-retrained-candidate for reference. Next gains
need a new signal (another backbone or frequency-domain features), not more OpenFake samples.

## Changelog

### 1.7.0 - 2026-10-16

Provenance traces become proof.

- `metadata` 1.7.0 reads C2PA through `analyzers/content_credentials.py` with the official C2PA trust
  list plus the frozen interim list vendored in `analyzers/trust/c2pa-trust-anchors.pem` (Google,
  Adobe, Microsoft, Truepic, camera makers). `c2pa-python` was an optional extra and was never
  installed in the image, so C2PA had been silently skipped; it is now a main dependency.
- `trainedAlgorithmicMedia` = generated, `compositeWithTrainedAlgorithmicMedia` / `compositeSynthetic`
  = AI-edited (suspicious only), plain `algorithmicMedia` (procedural) is no longer counted as AI.
- `analyzers/watermarks.py` decodes the imwatermark dwtDct marks of SDXL, FLUX.1 (BFL reference
  code), SD 1.x and SD 2.x. 0 hits on 1350 real photos across all datasets, 15 ms per image; the mark
  survives PNG but not JPEG re-encoding.
- New rule: `provenance_proof` (Trusted C2PA declaring generation, or a decoded watermark) returns
  `fake` with score >= 0.95 regardless of the bench. Untrusted or tampered credentials still vote
  through `metadata` as before.
- SynthID (Google, also OpenAI since 2026) has no public API; the result page links to synthid.com.
- `openfake_test` unchanged (all files are stripped of credentials and marks): 107/145, real -> fake
  0/100.
- Vision member experiments the same day (7b at 672 px, 1024 px, crop of the region the retrained
  detector found most suspicious): none changed a single Tribunal verdict on the 38 AI images the
  bench misses (1/38 each), so the vision member stays an explainer.

### 1.6.1 - 2026-10-14

Image fixes after a real press photo (Nikon D3S EXIF, plain studio background) came out
`suspicious` at 0.36.

- `metadata` 1.6.0: a camera signature plus a date mismatch alone (photo exported or edited days
  after capture) is `inconclusive`, not `suspicious`. The date note stays in the evidence. AI tool,
  generation parameters, C2PA AI and two strong flags behave as before.
- `ai_detector` 2.1.0: images with a camera signature skip the screenshot pre-filter, so studio
  portraits with a flat background are scored instead of abstaining. `content_check.camera_exif`
  records it.
- Aggregation: a `suspicious` band (score 0.35 to 0.5) without a single confident fake or
  suspicious voter becomes `inconclusive`. Lukewarm averages that lean real no longer read as
  suspicion.
- Measured on the production worker (full roster) on `openfake_test`, same 245 images as every
  earlier version:

| set | version | ensemble AUC | AI caught (fake+likely) | AI called authentic | real called fake | real suspicious |
|---|---|---|---|---|---|---|
| openfake_test | 1.3-1.6 | 0.998 | 108/145 | 6 | 0/100 | 1 |
| openfake_test | **1.6.1** | 0.997 | 107/145 | **5** | **0/100** | **0** |

  Hardest generators stay flux.2-klein-9b (25%), veo-3 (38%) and sora-2 (43%).
- `ai_detector` 2.2.0: the screenshot gate now rejects only images with fewer than 800 colours
  (64 levels per channel) or with 8 colours covering more than 70% of the frame. The old rule
  (more than 4000 colours, entropy and edge thresholds) rejected 51 of 100 real photos and 70 of
  145 AI images on `openfake_test`, so the ensemble sat out half of all images. The new rule
  rejects 0 real photos and 6 near-flat AI images; UI screenshots and charts are still rejected.
  A/B on the same local roster: ensemble scores 239 instead of 124 images, real -> likely_fake
  1 -> 0, AI caught 58 -> 58, ensemble AUC 0.878 -> 0.884.
- `llm_vision` 1.1.0: "no defect visible" (`human_photo`) no longer votes authentic; the vision
  model abstains unless it names a concrete defect. A ChatGPT portrait got an authentic vote from
  it while the verdict was likely AI.

### 1.6 - 2026-10-14

Text only; image roster unchanged.

- `text_classifier` v4: trained with humanizer-style attack rewrites (paraphrase, bypass, student,
  translate), chat wrappers stripped from AI rows, and symmetric typo / lowercase / no-punctuation
  noise on 30% of crops. Same frozen test split, flagged at t1:

  | | v3 | v4 |
  |---|---|---|
  | AUC en / ru / fr | 0.977 / 0.9995 / 0.995 | 0.988 / 0.998 / 0.995 |
  | human essays flagged en / ru / fr | 0% / 0.7% / 2.3% | 0% / 1.3% / 2.3% |
  | en AI, lowercase / no punctuation | 63% / 31% | 97% / 95% |
  | ru AI, lowercase / no punctuation | 73% / 65% | 98% / 99% |
  | fr humanized AI, no punctuation | 6% | 94% |
  | en textsight-2026 frontier AI | 36% | 50% |
  | en human Wikipedia prose | 1.3% / 9.7% | 3.3% / 13.5% |

  Knots still cap at 0.89, so the classifier alone never convicts.
- New context members (never vote, a flag means human review): `text_citations` (invented sources,
  reference format), `text_genre` (text type), `text_shadow` (closeness to AI answers to the
  assignment).
- Personal comparisons (`text_grade_fit`, `text_style`) need three earlier works of the student and
  compare with the student's own level, so strong students are not flagged.
- Known gap: no Russian school essays in training or calibration. Hand-written test texts in a
  student voice by an AI were flagged (correctly), but the false-positive rate on real Russian
  children's essays is not measured yet.

### 1.5 - 2026-10-14

Text: `llm_text` (prompted qwen2.5:3b) leaves the roster, `text_classifier` (weight 2.5) joins.
Image roster unchanged.

- `llm_text` measured offline on the text test split was inverted (en: 266/409 humans called AI,
  618/851 AI texts called human). With `text_evasion` it flagged 79% / 65% / 37% of en / fr / ru
  human essays and 4-41% of AI texts.
- `text_classifier`: fine-tuned multilingual-e5-small, logit-margin score, per-language knots
  capped at 0.89, so it alone gives `suspicious` at most. Same test split through `aggregate()`:
  human -> fake 0 in every group, human flagged 2.8% / 4.3% / 2.0%, human wiki prose 3-16%, AI
  flagged 91-100% across fresh, humanized, wiki-style and held-out gemma3-12b texts. Details in
  [[concepts/text-signals]].

### 1.4 - 2026-10-13

Text members for Classroom. Image roster unchanged, so the image numbers of 1.3 still hold.

- `text_evasion` (weight 2.0): homoglyphs from another alphabet inside words, invisible
  characters, odd spaces, Unicode tags, DOCX runs that are hidden, white or under 2pt. Votes a
  probability only when it finds something (0.6-0.97); otherwise abstains. Can convict only with
  a second voter (share rule).
- `text_grade_fit` and `text_style` are **context members** (`aggregator.CONTEXT_ANALYZERS`):
  never in the score or the vote. A flag (`suspicious`, confidence >= 0.6) turns authentic /
  inconclusive into `needs_review`. See [[concepts/text-signals]].

### 1.3 - 2026-10-13
New member [[analyzers/clip-probe]] (weight 2.5): a logistic-regression probe on the CLIP
ViT-B/32 embedding that provenance already stores, so it costs one dot product. First member
on a backbone different from community_forensics / custom_detector. Calibrated with a step just
above the highest real-photo score.

| set | version | ensemble AUC | AI caught | AI called authentic | real called fake | real suspicious |
|---|---|---|---|---|---|---|
| openfake_test | 1.2 | 0.995 | 97/145 (67%) | 9 | 0/100 | 1 |
| openfake_test | **1.3** | **0.998** | **108/145 (74%)** | **6** | **0/100** | 1 |
| diffusiondb | 1.3 | 1.000 | 60/60 | 0 | 0/60 | 0 |

The blind spots moved: gpt-image-2 0% -> 50%, sora-2 29% -> 43%, veo-3 25% -> 38%; flux.2-klein
stays at 25% and is the weakest generator now.


### 1.2 - 2026-09-15
Calibration for the retrained member ([[analyzers/custom_detector]]): `calibration.json`
next to the weights maps everything a real photo ever scored (<= 0.975) to <= 0.50 and lifts
0.98+ to 0.80+. Weights and rules unchanged, so the roster fingerprint is still `352aa7ef3234`
- the fingerprint covers roster and weights, not model artefacts; the model dir carries its own
`training_meta.json` and `calibration.json`.

| set | version | ensemble AUC | AI caught | AI called authentic | real called fake | real suspicious |
|---|---|---|---|---|---|---|
| openfake_test | 1.1 | 0.993 | 103/145 (71%) | 4 | 0/100 | 8 |
| openfake_test | **1.2** | **0.995** | 97/145 (67%) | 9 | **0/100** | **1** |
| diffusiondb | 1.2 | 1.000 | 60/60 | 0 | 0/60 | 0 |

A deliberate trade: seven fewer real photos flagged `suspicious` for six fewer catches and five
more misses. Validated on a generator + real-photo split before shipping. Weak generators
unchanged: gpt-image-2 0/6, flux.2 2/8, veo-3 2/8, sora-2 2/7.


### 1.1 - 2026-09-04
The retrain release. `custom_detector` is now fine-tuned from the community_forensics backbone
on 400 real / 736 AI images spanning 20 current generators ([[analyzers/custom_detector]]);
its held-out AUC went 0.711 -> **0.993**. Weights: custom_detector 1.5 -> **3.5**, ai_detector
1.5 -> **1.0**, community_forensics 3.5 (unchanged), metadata 1.5, ela 0.75. New rule: a lone
fake voter carries the verdict when it holds >= 50% of the confident-voter weight and p >= 0.9
([[concepts/aggregation]]).

Measured on `dataset/openfake_test` - a second OpenFake pull, perceptual-hash deduplicated
against the training tree, 100 real / 145 AI, 20 generators, never seen in training:

| set | version | ensemble AUC | AI caught (fake+likely) | AI called authentic | real called fake | real suspicious |
|---|---|---|---|---|---|---|
| openfake_test | 1.0 | 0.916 (acc 0.776) | 34/145 (23%) | 39 (27%) | 0/100 | 2 |
| openfake_test | **1.1** | **0.993** (acc 0.951) | **103/145 (71%)** | **4 (3%)** | **0/100** | 8 |
| diffusiondb | 1.1 | 1.000 | 60/60 | 0 | 0/60 | 0 |

Per generator (1.1, confirmed by rerun): midjourney-7, ideogram-2.0, illustrious, lumina,
recraft-v2, aurora, halfmoon at 100%; z-image-turbo 7/8; frames, gpt-image-1.5, nano-banana-pro,
recraft-v3, seedream-v5 6/8. Still weak: gpt-image-2 1/6, flux.2-klein-9b 2/8, veo-3 2/8, sora-2 2/7 -
the retrained member sees them (0.83-0.998) but community_forensics scores them near real and
outweighs it. Next lever is either a second modern-trained member or a CF retrain.

Cost of the recall: real photos called `suspicious` went 2 -> 8 of 100. None called fake.


### 1.0 - 2026-09-04
Members (image): community_forensics 3.5 (calibrated), custom_detector 1.5, ai_detector 1.5,
metadata 1.5, ela 0.75 (manipulation channel only). Video: video_frame 2.0. Audio:
audio_spectrogram 2.0. Text: llm_text 2.5. Vision LLM: llm_vision 1.5.
Rules: evidence-sourced probabilities, weight-share disagreement (>= 2 voters per camp, lighter
camp >= 30%), CF priority override with custom/ai_detector as peers, ELA never votes on the AI
axis. Not members: npr_detector (AUC 0.499 on diffusion), siglip_detector (35% real-photo FP),
face_deepfake_detector (AUC 0.181 on OpenFake).

| set | ensemble AUC | acc | AI caught (fake+likely) | AI called authentic | real called fake |
|---|---|---|---|---|---|
| diffusiondb 60/60 | 1.000 | 1.000 | 56/60 | 0 | 0 |
| OpenFake 150/236 | 0.890 | 0.777 | 64/236 (27%) | 57 (24%) | 0 |

Known blind spots: flux.2-klein-9b and sora-2 (0% caught), gpt-image-2 and midjourney-7 (8%).
Full derivation in [[fixes/audit-2026-08]].

## See also

- [[analyzers/_index]] - the roster with weights
- [[concepts/detector-evaluation]] - how a version gets its numbers
