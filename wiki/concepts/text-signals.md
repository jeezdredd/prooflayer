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
