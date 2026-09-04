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
- `GET /api/v1/system/status/` -> `services.analyzers.ensemble` = `"Tribunal 1.0"` next to the
  roster-drift probe ([[api/system-status]]).
- `manage.py eval_detectors` prints the label and fingerprint in its header.

## Versioning

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

## Changelog

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
