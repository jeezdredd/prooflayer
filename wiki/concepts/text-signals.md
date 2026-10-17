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
| `text_evasion` | `scan_text`: mixed-script words (minority letters must be look-alikes, so "IT-компания" is fine), zero-width and other invisible chars (leading BOM ignored), odd spaces, tag chars; `scan_docx`: runs with `w:vanish`, white colour without dark highlight/shading, size < 2pt; since 1.1.0 (2026-10-16) also look-alike punctuation, stray combining marks on common en/ru/fr words (wordfreq) and styled / fullwidth / circled letters inside words, 0 hits on 1955 human essays and 3155 Wikipedia paragraphs | `ai_probability` 0.6-0.97 when found, else abstains |
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

## Phase T4: supervised classifier `text_classifier` (2026-10-14, Tribunal 1.5)

`intfloat/multilingual-e5-small` fine-tuned as a two-class head (`train_text_classifier`) on
`dataset/text_t4` (`build_text_train`): legacy human/AI corpora (DAIGT, COLING, CoAT, MMGT),
fresh MLX generations (qwen3-4b, gemma3-4b, qwen2.5-7b, llama3.2-3b; gemma3-12b held out for test
only), LLM-humanized rewrites of them, 1000 pre-2022 Wikipedia passages per language
(`scripts/fetch_wiki_paragraphs.py`, revisions as of 2021-12-31) and matching wiki-style AI
generations on the same titles. 14.3k train rows, group-balanced over (lang, label), random
window and random length crops so text length cannot act as a label.

Inference: `analyzers/text/classifier.py`, up to 4 windows of 512 tokens, score = mean logit
margin (logit AI minus logit human; probabilities saturated at 0.9967). Calibration per language
on the calib split: `t1` = 99th percentile of calib human, knots map the margin to
`ai_probability` and top out at **0.89** (`--no-strict`), so the classifier alone never reaches
the aggregator's single-voter 0.9 floor: on its own it can only say `suspicious`. A `fake` needs a
second voter (in practice `text_evasion`). Short texts (< 120 tokens) abstain. Model lives in
`RETRAIN_MODEL_DIR/text` (`make ship-text`).

Test split (frozen `text_eval` test plus new held-out rows), classifier alone at `t1`:

| lang | AUC | human FPR | wiki-pre2022 human | AI caught (fresh, humanized, wiki, held-out gemma3-12b) |
|---|---|---|---|---|
| en | 0.977 | 0% (n=254) | 1.3%; textsight wiki 9.7% | 94-100%; textsight-2026 36%, old Claude 36-52% |
| ru | 0.9995 | 0.7% (n=298) | 0% | 97-100% |
| fr | 0.995 | 2.3% (n=300) | 3.2% | 99-100% |

Through the real `aggregate()` with `text_evasion` (sim over the same test rows):

| | prod before (llm_text + evasion) | 1.5 (text_classifier 2.5 + evasion) |
|---|---|---|
| human -> fake | 0 (ru wiki 1/140) | **0 in every group** |
| human flagged en / fr / ru | 79% / 65% / 37% | 2.8% / 4.3% / 2.0% |
| human wiki text flagged | 43-65% | 3-16% |
| AI flagged (generate, humanize, wiki) | 4-41% | 91-100% |
| AI with character evasion -> fake | 22-35% | 32-39% |

`llm_text` was replicated offline (same qwen2.5:3b prompt via MLX) and turned out **inverted**:
it called 266/409 en human essays AI and 618/851 en AI texts human, with fr and ru alike. It is
removed from the roster. Keeping it next to the classifier converted classifier false positives
into `fake` (fr human 1.3%, wiki up to 3.2%).

Earlier attempts: an allow-alone-fake "strict" threshold at the max calib human margin failed,
because margins pile up near the ceiling (t1 5.65, strict 5.76) and 4/155 textsight wiki humans
landed above it. Open: textsight-2026 en (frontier models) is caught only 36-39%; encyclopedic
human prose still gets `suspicious` up to 16%.

## Sources, citation format and text type (2026-10-14)

Two more **context members** (`aggregator.CONTEXT_ANALYZERS`, never in the vote):

- `text_citations` (`analyzers/text/citations.py`): extracts DOIs, arXiv ids, ISBNs (bad check digit
  is reported as invented without a lookup), links, reference-list entries and long quotes, then
  checks them in parallel: doi.org handle API, arXiv API, Open Library then Google Books, OpenAlex
  by guessed title then Crossref by full entry, links through `safe_get` (SSRF-safe; a domain that
  does not resolve counts as missing, a private address is never fetched or blamed), quotes through
  the plagiarism search chain. Weighted missing share (DOI/arXiv/ISBN 1.0, reference 0.6, link 0.4,
  quote 0.25); `suspicious` when missing weight >= 1.0 and share >= 34%, which turns an authentic or
  inconclusive verdict into `needs_review`. Live check: real ru books (Выготский, Лотман,
  Ключевский), Bourdieu, Goodfellow, Kahneman found; invented DOI and invented books missing.
- Citation format (`analyzers/text/citation_style.py`, inside `text_citations` evidence `format`):
  per entry style detection and concrete fixes for APA 7, MLA 9, Chicago, Harvard, IEEE, Vancouver,
  ГОСТ Р 7.0.100-2018 (Cyrillic entries) and ISO 690; list level: mixed styles, alphabetical or
  numeric order, in-text citation form vs style, author-year citations missing from the list,
  numbered citations beyond the list. Formatting never affects the verdict.
- `text_genre` (`analyzers/text/genre.py`): cue phrases and structure per language pick argument
  essay, narrative, retelling, literary analysis, description, report, letter or poem (else general
  text), with the cues shown to the teacher. A report with no sources gets a note; an essay or a
  retelling without sources is normal.

## Per-passage scores and attack-robust training (2026-10-14)

- `text_classifier` evidence now carries `segments` (paragraphs, or groups of three sentences, merged
  to at least 40 words, up to 12) with their own `ai_probability` through the same knots, and
  `segment_spread`. The report draws a bar per passage and says when some passages read far more
  machine-like than others (spread >= 0.5). Display only: passage-level calibration is not done, so
  it never changes the verdict.
- Training data: `generate_text_ai.py --mode attack` writes humanizer-style rewrites
  (`attack:paraphrase` QuillBot-like, `attack:bypass` StealthGPT/Undetectable-like perplexity and
  burstiness prompt, `attack:student`, `attack:translate` en<->ru/fr, `attack:recursive` test only).
  `build_text_train` strips chat wrappers ("Okay, here's an essay...:", "Would you like me to...")
  that leaked into ~270 gemma generations and made AI rows trivially separable.
- `train_text_classifier` applies symmetric noise (typos, lowercase, stripped punctuation) to 30% of
  crops of both classes. v3 measured: lowercase dropped en AI recall 96% -> 71%, stripped punctuation
  96% -> 46% (ru 98% -> 69%); human flags did not rise.

## Humanizer-robust classifier t6 (2026-10-16, Tribunal 1.8.0, `text_classifier` 1.1.0)

Training set `dataset/text_t6` (18 163 rows, e5-small, 2 epochs, max-len 384) adds two sources to t4:
- `_humanizers`: HumanizerBench + AI Humanizer Benchmark (CC-BY-4.0, `dataset/humanizers/all.jsonl`,
  2 381 pairs from 24 tools). Six tools are held out of training entirely: humbot, undetectable,
  stealth-writer, walter-writes, gptinf, notegpt. Other tools split by input hash 60/15/25.
- `dataset/text_gen/adversarial.jsonl` (251 rows): `scripts/adversarial_paraphrase.py`, the Cheng et al.
  2025 detector-guided paraphrase attack against our own t4 with an MLX paraphraser.

Compared with `scripts/eval_humanizers.py <model>...` (en threshold = each model's `threshold_fpr1`):

| model | 6 held-out humanizers (612) | seen tools, unseen texts (442) | adversarial test en / fr / ru |
|---|---|---|---|
| t4 (prod before) | 49% | 52% | 50 / 62 / 67% |
| t5b (humanizers only) | 87% | 81% | 43 / 62 / 62% |
| **t6 (shipped)** | **91%** | **86%** | **57 / 72 / 67%** |

Human texts flagged (ai_probability >= 0.5, which is what `suspicious` uses), test split:
en student essays (DAIGT) 2/254 = 0.8% (t4 1.6%); ru CoAT 1.7% (t4 3.0%); fr news 7.3% (t4 4.7%,
t5b 4.3%: a regression); pre-2022 Wikipedia en 7.9%, fr 7.1%, ru 5.0%; TextSight encyclopedic
Wikipedia en ~28% for every model (known weak spot: encyclopedic register reads machine-like).
Weaker than t4 on English character attacks (homoglyph 63 -> 42%) and some small legacy generator
groups; `text_evasion` still catches the character tricks. Shipped with `make ship-text
TEXT_DIR=dataset/text_models/e5-small-t6`.

## Style compared within the same kind of text (2026-10-16, `text_style` 1.1.0, Tribunal 1.9.1)

Demo run showed a false flag: Sam's formal report vs three casual reflections drifted 0.80 (threshold 0.6)
-> needs_review, while AI essays vs kid narratives drifted only 0.07-0.59 (cross-genre drift caught
nothing useful). `TextStyleAnalyzer` now maps `detect_genre` to a group (`STYLE_GROUPS`: narrative,
description, letter, retelling -> personal; argument, analysis, report, other -> expository; poem) and
compares only with earlier profiles of the same language and group (`profile["group"]`; old profiles
without a group are ignored). Fewer than 3 -> inconclusive with "style is only compared with the same
kind of text"; the UI names the group. The simple-writer-hands-in-polished-essay case is left to
`text_grade_fit` and `text_classifier` (Dmitry in the demo: style 0.80 within his own argument essays,
grade fit 0.76 vs his usual 0.0, classifier p=0.89). Genre detection on short kid essays is noisy
(some arguments read as narratives), so the group split is coarse on purpose.

## Academic register, model t7 (2026-10-17, Tribunal 1.9.0, `text_classifier` 1.2.0)

Frozen human sets in `dataset/text_eval_academic/` (pre-2022): arXiv and PubMed abstracts + body chunks
(`ccdv/*-summarization` test), Russian abstracts (`ai-forever/ru-scibench-grnti-classification` test,
`mlsa-iai-msu-lab/ru_sci_bench` first rows), Gazeta.ru and CNN news. t6 flagged (ai_probability >= 0.5)
40.5% / 49% of Russian abstracts, 0% of English academic text.

Fix: `scripts/fetch_academic_texts.py` -> `dataset/text_academic/human.jsonl` (3083 human texts, disjoint
from the frozen sets, hash split) + `dataset/text_gen/academic_seeds.jsonl` (real titles as hints);
`generate_text_ai.py` genres `academic-abstract` / `academic-body`; ~2700 AI texts (gemma3-4b, qwen3-4b,
qwen2.5-7b train/calib; gemma3-12b test only) + bypass/student attacks. `build_text_train` caps each
academic family at 20% (AI 30%) so calibration keeps essays and wiki. `dataset/text_t7`, 20 563 rows.

| flagged human | t6 | t7 |
|---|---|---|
| ru abstracts GRNTI / RuSciBench (frozen) | 40.5% / 49% | 2.5% / 9% |
| ru wiki-pre2022 (test) | 5.0% | 0% |
| ru CoAT essays (test) | 1.7% | 2.0% |
| en DAIGT essays (test) | 0.8% | 1.2% |
| en wiki-pre2022 (test) | 7.9% | 12.6% |
| en TextSight encyclopedic (test) | 28.4% | 32.9% |
| en CNN news (frozen) | 2.5% | 5.5% |
| ru Gazeta news (frozen) | 1.5% | 0.5% |
| en academic arXiv / PubMed | 0% | 0% |

Recall: held-out humanizers 91 -> 90%, seen 86 -> 90%, adversarial en/fr/ru 57/72/67 -> 67/90/71%,
academic AI en 100%, ru 97-100% (gemma3-12b unseen 97%), llama3.2 78 -> 84%, qwen2.5 91 -> 96%.
**Open:** English encyclopedic and news register got worse; next model should add English news and
encyclopedic human text the same way.

## Russian sources and GOST references (2026-10-16)

Live check on 26 real sources: English 12/12 found, Russian books without DOI 1/14 found, so every
Russian essay with a real bibliography was flagged "cited sources that do not exist". Two causes:
OpenAlex/Crossref barely cover Russian books, and `guess_title` only parsed English formats, so a GOST
entry ("Ключевский В. О. Курс русской истории. М.: Мысль, 1987.") went to search as a whole string.
Fix in `analyzers/text/citations.py`: `GOST_AUTHORS`/`GOST_TAIL` cut authors and the city/publisher tail;
`check_bibliography` falls back to web search (`plagiarism.search`, title in quotes, 80% word cover);
a Cyrillic entry found nowhere stays `unchecked`, never `missing`. After: Russian 13/14 found, 1
unchecked, 0 missing; English unchanged. Fake English references are still caught.

## Personal baselines before any personal flag (2026-10-14)

Signals that compare a student with themselves or the class never flag on one or two works:

- `text_grade_fit`: a text above the class level is only `suspicious` when the student has at least
  3 earlier class works in the same language and this one is 0.3+ mismatch above their own median.
  With fewer works the evidence carries `baseline: {have, need}` and the finding says there is not
  enough data; a student whose earlier work is also above level is not flagged.
- `text_style`: needs 3 earlier works (was 2).
- Class radar: level jumps need 3 earlier works; shared skeletons need 5 works from 4 students in the
  window, otherwise the panel shows how much data is missing.

Single-work evidence (classifier, bypass tricks, invented sources) is still read on one work, and none
of it convicts alone.
