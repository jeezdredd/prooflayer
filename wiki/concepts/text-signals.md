---
type: concept
created: 2026-10-13
source: backend/analyzers/text/, backend/analyzers/implementations/text_signals.py, frontend/src/components/TextReport.tsx
---

# Text signals (Phase T1)

Deterministic checks for student writing in ru / en / fr. Each language is a `Language` entry in
`analyzers/text/language.py` (stopwords, function words, vowels, readability formula); adding a
language means adding an entry plus phrasebook lines.

| member | what it reads | output |
|---|---|---|
| `text_evasion` | `scan_text`: mixed-script words (minority letters must be look-alikes, so "IT-компания" is fine), zero-width and other invisible chars (leading BOM ignored), odd spaces, tag chars; `scan_docx`: runs with `w:vanish`, white colour without dark highlight/shading, size < 2pt | `ai_probability` 0.6-0.97 when found, else abstains |
| `text_grade_fit` | `Classroom.level` (1-11 school year, 12-17 university year 1-6), share of content words below a level-dependent `wordfreq` zipf threshold (3.6 for grades 1-4 down to 2.1 at university), readability grade (en Flesch-Kincaid, ru Flesch-Kincaid adapted, fr Kandel-Moles mapped) | `mismatch` 0-1, list of beyond-level words |
| `text_style` | profile per text (sentence length mean/std, word length, MATTR, rare share, punctuation rates, function-word profile) stored in the result evidence; compared with up to 8 earlier class submissions of the same student in the same language (needs 2) | drift 0-1; also the LLM phrasebook density |

Hand checks: an academic paragraph on "декомпозиция" scores mismatch 1.0 at grade 5, 0.84 at
grade 8, 0.3 at university year 2; children's texts in all three languages score 0.

Limits: thresholds are hand-set, not yet calibrated on real student essays; grade formulas for
ru/fr are approximations. The UI says these are reasons to talk to the student. Calibration and
the statistical detector come in T3 (see the plan in `~/.claude/plans/groovy-popping-prism.md`).

Teacher UI: class year selector on class creation and in the class header; `TextReport` on the
result page lists each finding with the offending words.

## Phase T3: Binoculars statistical detector (2026-10-13, not shipped)

`analyzers/text/binoculars.py` scores text as performer log-perplexity over observer/performer
cross-perplexity (Hans et al. 2024), 512-token windows, lower means more machine-like.
`eval_text_detectors` scores `dataset/text_eval`, sets per-language thresholds on the calib split
(1% and 5% human FPR) and writes monotone knots; `text_binoculars` reads them. The analyzer is
written and tested but **not registered in `seed_analyzers`**, because the measurement failed.

Qwen3-1.7B-Base / Qwen3-1.7B, 150 texts per class per split, threshold at 1% human FPR on calib:

| lang | AUC | AI caught @1% | human flagged on test | humanized caught |
|---|---|---|---|---|
| en (DAIGT essays) | 0.66 | 37% | 4.0% | 5-44% by mode |
| en textsight 2026 | | 12% | 11% of human wiki text | |
| ru (CoAT) | 0.09 (inverted) | 0% | 4.0% | 0% |
| fr (MMGT rewrites) | 0.80 | 4% | 0% | 0% |

Reading: small-model Binoculars does not separate 2026 generators from human text, the 1% human
threshold does not transfer across domains (4% on test essays, 11% on wiki text), and Russian is
inverted on CoAT (machine texts score *higher*), which is a dataset artifact, not a usable rule.
Shipping it would add false accusations. Next step is T4, a supervised multilingual classifier
trained on current generators plus humanized variants, measured on the same frozen test split.
Scores are cached in `dataset/text_scores/` so later pairs can be compared without rescoring.
Prod note: two 1.7B models per Celery child do not fit the 16 GB worker at concurrency 4; any
model-based text member needs its own single-slot queue.
