# Ingest Log

Newest at top.

## [2026-10-26] originality-papers-review | Review fixes: PDF hyphenation, title mask, paper identity, time caps, arXiv PDF pacing

- Source: review of `feat/openalex-arxiv` (diff against main, live smoke against the public OpenAlex, arXiv and Wikipedia APIs from the dev machine, arxiv.org robots.txt, arXiv API terms of use)
- Backend: `plagiarism.web.join_line_breaks` joins words split by a line-break hyphen in PDF text; `title_skip` masks a paper's own title in the work for that paper; `plagiarism.academic.paper_keys` (title, arXiv id from abs/pdf links and the `10.48550/arXiv` DOI, DOI) dedupes papers within and across catalogues; arXiv PDFs on their own 15 s slots (`plag:arxiv_pdf:turn:*`); `fetch_text` stops after 30 s, the web page loop after 150 s, paper full texts after 90 s; full texts cached zlib-compressed; `BIBLIOGRAPHY_RE` adds Источники, Использованные источники, Sources, Literature, Literature cited, Sources et références; PDF report scope names only the catalogues that answered
- Checks: 9 new tests in `plagiarism/tests/test_academic.py` (each of the four behaviour tests fails with its fix removed), report scope test extended; live smoke on 6 texts (LoRA abstract copy, Russian journal PDF body copy, Russian abstract copy, honest essay, essay naming LoRA, honest Russian essay naming a paper title)
- Pages updated: [[services/originality]], [[hot]]

## [2026-10-26] originality-papers | Copy check searches OpenAlex and arXiv; paper sources with authors, year, venue

- Source: owner decision (web search stays free: Wikipedia, OpenAlex, arXiv, later an own index; no paid APIs, signups, key-only services or scraping), prod SearXNG engines all blocked, OpenAlex docs (search covers title, abstract, full text; keyless budget $0.10/day per IP, search $0.001, optional free key 10x), arXiv API guidance (one request per 3 s), live probes of both APIs
- Backend: new `plagiarism.academic` (8-word key phrases, OR groups under a URL budget, OpenAlex works search with abstract rebuilt from the inverted index and open-access/CyberLeninka full-text links, arXiv Atom parsing, Redis-slot pacing for arXiv and its PDFs, 429/low-credit pauses, 7-day cache); `plagiarism.web` reads PDFs through `common.documents.extract_pdf` (15 MB, 60 pages), caches paper full texts, tags every web match with `engine`, drops an engine whose pages never opened; arXiv record wins a title collision; serializer and PDF report show authors, year and venue, PDF scope names the engines
- Settings: `PLAGIARISM_WIKIPEDIA`, `PLAGIARISM_OPENALEX`, `PLAGIARISM_ARXIV` (on, off in tests), `OPENALEX_API_KEY` (optional), `OPENALEX_MAILTO`, hits, timeouts, full-text budget, cache TTL; compose passes the switches and the key
- Frontend: scope sentence built from `web_engines` ("Wikipedia, open scientific papers and a web search"), paper rows "Scientific paper · authors · year · venue", headline "found in scientific papers"; landing originality line, school web search setting, Privacy and Data Processing (en/ru) name Wikipedia, OpenAlex and arXiv
- Checks: `plagiarism/tests/test_academic.py` (31 tests, mocked HTTP), report scope test; live smoke from the dev machine: Transformer abstract copy found on arXiv (PDF read) plus three OpenAlex papers in 9 s, Russian copy from a CyberLeninka paper body found through OpenAlex full-text search (512 chars)
- Pages updated: [[services/originality]], [[infrastructure/env-vars]], [[hot]]

## [2026-10-24] demo-t5 | Demo shows what the accounts doc says; seed_demo keeps passwords, redates and verifies (Tribunal 1.10.1)

- Source: audit theme t5-demo (findings 63, 88-102), owner decisions, local seed simulation with the real analyzers (t7, e5-small, image detectors), Wikipedia lookup for Polina's paste
- Product: `text_classifier` 1.4.0 returns `inconclusive` for p >= 0.5 below the fpr1 line, so the chatbot chip only appears above the 1-in-100 line; DOCX hidden runs (`evasion.hidden_docx_texts` / `strip_hidden`) are left out of originality; the headline names the main source when originality < 60 (`top_source` on class rows for supervisors only, PDF report too); class batches take a per-file student map (`students` JSON, SubmitPage asks "Чья работа в каждом файле?")
- seed_demo: passwords = base64url(HMAC-SHA256(DEMO_PASSWORD_SECRET or SECRET_KEY, email))[:12], `--rotate-passwords` for random ones; `--redate` shifts demo works, reports, overrides, batches, AI answers and objections (due dates recomputed) so the newest work is a day old; `--verify` waits for reports and prints a table against the per-work `expect` blocks, exit 1 on a mismatch; objections dated before their work are refused, answered ones are filed a day after the work and answered a day later
- Demo data: honest baselines of Dmitry, Maria, Ivan, Kirill and Anna's PDF rewritten (t7 p 0.07-0.28, passage spread under 0.5); batches "· ответы с листков" hold an honest, an AI and a copied answer; Lev's Onegin essay trips the age check; Timofey's hidden instruction is English; Polina hands in a CC0 DiffusionDB drawing with a damaged SD 1.x watermark; Anna adds a CC0 camera photo of the Peter and Paul Fortress; Jordan's essay ends on a full sentence; Anna's objection to a match that no longer exists removed
- Checks: `classroom/tests/test_demo_data.py` (evasion, genre, age, style, shingle copies, t7 bands when the model is present); local simulation: 82 of 83 works match their expect block, the last one (Polina's Wikipedia paste) matches when Wikipedia search is on (19.7% original)
- Pages updated: [[services/classroom]], [[hot]]

## [2026-10-24] teacher-ui-audit | Result page, text checks and originality speak plainly (Tribunal 1.10.0)

- Source: owner review of the demo as a non-technical teacher ("20 класс", false rare words, copy sources not visible), 104 confirmed audit findings in four themes (result page, text checks, originality, class pages), demo seed-order simulation with the real e5-small model
- Result page: class work gets a plain header (student, class, date, file type in Russian units), no risk %, no hash; voting, report and publish buttons hidden for class work; rights come from `viewer_role`, `can_object`, `can_publish`; one `MediaSummary` for pictures, audio and video (watermark proof names the generator, tallies only when a check flagged); class PDF uses the school plan and plain file types
- Text checks: rare words judged by whole-word frequency (`grade.lexeme_zipf`), look-alike letters normalised first; Russian readability shown as plain / textbook / adult text, never a grade number; style drift shown as now/earlier numbers; genre "many dates" counts numbers outside the reference list (3 or more); citation first author needs initials or a first name; shadow answers created after hand-in are skipped
- Originality: copied runs need 8+ words, links and DOIs dropped, wording shared by many classmates and the assignment prompt masked; percentages count whole-word letters, sources under 60 letters or 0.6% dropped; each excerpt carries the source passage (`source_excerpts`); reworded sentences fold into the exact match of the same source; `web_status` ok / failed / short / off (migration 0003); bibliography excluded
- Demo simulation: every honest demo work comes out 100% original; only Vera from Arina, Olga from Ivan and the two hidden-text DOCX still match
- Deploy needs `seed_demo --reset` so stored demo evidence is rebuilt with the new analyzer versions
- Pages updated: [[concepts/text-signals]], [[services/originality]], [[hot]]

## [2026-10-24] class-pages-act | Class pages show names, agree with their chips, and objections clear work

- Source: owner demo review as a teacher (audit theme t4-class-pages), classroom/attention.py, classroom/export.py, content/objections.py apply_decision, radar examples
- Pages updated: [[services/classroom]], [[hot]]

## [2026-10-24] email-resend | Resend key now reaches the prod containers

- Source: public /api/v1/system/status/ (email backend smtp), deploy/compose.prod.yml environment blocks, settings/base.py backend order
- Pages updated: [[infrastructure/env-vars]]

## [2026-10-17] class-page-plain | Class page in plain language; 9Б demo class filled; radar stricter

- Source: owner review of the demo as a non-technical teacher (radar "grade 20", nameless cluster lists, 9Б empty), local alignment measurements on demo essays, t7 scores on the 9Б texts
- Pages updated: [[services/classroom]], [[hot]]

## [2026-10-17] originality-web | Web search was blocked; Wikipedia full-text search added

- Source: prod SearXNG unresponsive_engines, local repro on the demo Wikipedia paste, plagiarism/search.py
- Pages updated: [[services/originality]]

## [2026-10-17] demo-all | Every Classroom feature in the demo; style compared within the same kind of text

- Source: prod demo seed review (Anna and Sam false flags), text_style 1.1.0, seed_demo (teachers, archived, batches, teacher checks, overdue objections)
- Pages updated: [[concepts/text-signals]], [[services/classroom]]

## [2026-10-17] demo | Demo shows humanizers, hidden DOCX text, teacher uploads, objections, AI traces

- Source: classroom/demo/demo_data.json, seed_demo (asset, uploaded_by_teacher, objection), scripts/build_demo_assets.py, local checks with t7
- Pages updated: [[services/classroom]]

## [2026-10-17] tribunal-1.9 | Text model t7 trained on academic prose

- Source: frozen academic/news FPR check, scripts/fetch_academic_texts.py, academic generation, text_t7, t6 vs t7 comparison
- Pages updated: [[concepts/text-signals]], [[concepts/tribunal]], [[hot]]

## [2026-10-16] citations-ru | Real Russian books no longer flagged as invented

- Source: live check on 26 real sources (scripts in session), analyzers/text/citations.py, tests
- Pages updated: [[concepts/text-signals]]

## [2026-10-16] brand-landing | Tribunal stays Latin in Russian, real photos in the compare preview

- Source: ru.json (12 strings), reports/copy.py, api 0013 (roadmap + changelog ru fields), Workspace ReviewPreview with /samples/compare-{original,edited}.webp
- Pages updated: [[concepts/tribunal]]

## [2026-10-16] objections-copy | Objection form names the teacher only for class work

- Source: SubmissionDetailSerializer `in_class` (classroom_id set), ObjectionPanel copy: class work -> "Tell your teacher...", personal work -> "Tell our reviewers..."; "assessment" -> "verdict" everywhere in the panel
- Pages updated: [[concepts/privacy-and-data]]

## [2026-10-16] tribunal-1.8 | Humanizer-robust text classifier t6

- Source: train_text_classifier on dataset/text_t6, scripts/eval_humanizers.py (t4 / t5b / t6), scores.jsonl human flag rates
- Pages updated: [[concepts/text-signals]], [[concepts/tribunal]], [[hot]]

## [2026-10-16] ui | Motion effects, live analyzer checklist, lighter card style

- Source: f306ec3 (index.css, SearchingOrb, TaskSteps, UploadProgress, AnalyzerTimeline, Landing/Pricing/Upload/FactCheck pages), effects modelled on 21st.dev picks and built in-house
- Pages created: [[frontend/ui-motion]]
- Pages updated: [[hot]]

## [2026-10-16] text-humanizers | Humanizer benchmark data, adversarial paraphrase attack, eval script

- Source: f5a67cf (build_text_train `_humanizers` source, scripts/adversarial_paraphrase.py), scripts/eval_humanizers.py
- Pages updated: [[concepts/text-signals]]

## [2026-10-16] copy-landing | Plain-language landing and app copy, embed widget removed

- Source: 3dc0890, 29596ea, 371a05f, d20d1f7, c0c2693, 7d2d0c8, e7586c3, 2c7d861, b2d0559 (roadmap October refresh, api migrations 0009-0011)
- Pages updated: [[api/endpoints]], [[frontend/routes]], [[services/auth-email]], [[services/pricing]]

## [2026-10-16] pricing | Charm prices, yearly shown per month

- Source: 0e0fc69 (billing/plans.py, PricingPage)
- Pages updated: [[services/pricing]]

## [2026-10-16] classroom | Teacher uploads for a student, status pulse

- Source: c50a380 (Submission.uploaded_by, content 0019, `student=` on submissions/batches), 5ba2733 (StatusPulse)
- Pages updated: [[services/classroom]]

## [2026-10-16] tribunal-1.7 | AI traces: Content Credentials, generator watermarks, trace hiding

- Source: 10d3b6b (content_credentials, watermarks, metadata 1.7.0, provenance_proof rule), f31de63 (text_evasion 1.1.0, metadata 1.8.0)
- Pages updated: [[concepts/tribunal]], [[concepts/text-signals]]

## [2026-10-16] cache | Verdict cache keyed on Tribunal revision

- Source: a59770c (Submission.tribunal_revision), 44dbb32 (eval JSON keeps member evidence)
- Pages updated: [[concepts/submission-pipeline]]

## [2026-10-16] vision-gpu | Vision judge on the GPU via Vulkan, qwen2.5vl:7b

- Source: 9d087af, 94702fa, a3dc725 (compose.prod.yml, llm_vision 1.3.0, GPU guard unit)
- Pages updated: [[analyzers/llm-vision]], [[services/ollama]]

## [2026-10-15] reports-text | PDF reports redesign, highlighted passages, Russian roadmap, CI

- Source: c6bb29c, c6e25e1, 9a0890f, 8b64b4d, b6fcb7b
- Pages updated: none at the time (backfilled here)

## [2026-10-14] tribunal-1.6 | Attack-robust text classifier v4, classroom signals, student accounts

- Source: train_text_classifier v4, noise eval v3 vs v4, classroom radar/shadow, student access rules
- Pages updated: [[concepts/tribunal]], [[concepts/text-signals]], [[services/classroom]]

## [2026-10-14] text-sources | Ghost citations, citation format, text type

- Source: analyzers/text/citations.py, citation_style.py, genre.py, live API checks
- Pages updated: [[concepts/text-signals]]

## [2026-10-14] text-t4 | Supervised text classifier replaces llm_text (Tribunal 1.5)

- Source: train_text_classifier v3 on dataset/text_t4 with pre-2022 Wikipedia contrast pairs, offline llm_text replica, aggregate() simulation
- Pages updated: [[concepts/text-signals]], [[concepts/tribunal]], [[concepts/aggregation]], [[services/classroom]], [[services/celery-workers]]

## [2026-10-13] landing | Workspace showcase, editable roadmap, 3D brain

- Source: frontend landing rework, api.RoadmapItem
- Pages updated: [[api/endpoints]]

## [2026-10-13] text-t3 | Binoculars detector measured, not shipped

- Source: eval_text_detectors on dataset/text_eval with Qwen3-1.7B pair
- Pages updated: [[concepts/text-signals]]

## [2026-10-13] privacy-legal | Retention, deletion, consent, legal pages

- Source: code changes in content/users/analyzers/plagiarism/billing, two reviewer workflows over the legal pages
- Pages created: [[concepts/privacy-and-data]]
- Pages updated: [[hot]]

## [2026-10-13] originality | Plagiarism check with fingerprints, semantic and web matching

- Source: backend/plagiarism, live DDG test, e5 similarity probe (translations 0.93-0.95, unrelated 0.79)
- Pages created: [[services/originality]]
- Pages updated: [[hot]]

## [2026-10-13] text-signals | Evasion, age fit, style drift for student texts

- Source: backend/analyzers/text, text_signals.py, hand checks in three languages
- Pages created: [[concepts/text-signals]]
- Pages updated: [[concepts/tribunal]], [[hot]]

## [2026-10-13] pricing | Plan catalog, School and University tiers, Paddle price mapping

- Source: backend/billing (plans, views, models), PricingPage
- Pages created: [[services/pricing]]
- Pages updated: [[hot]]

## [2026-10-13] classroom-subdomain | Schools, classroom.prooflayer.cloud, admin supervision

- Source: backend/classroom (models, access, org_views), frontend/src/classroom, local browser run of anonymous, student and admin flows
- Pages updated: [[services/classroom]], [[hot]]

## [2026-09-15] tribunal-1.2-calibration | Per-model calibration file for the retrained detector

- Source: regenerated eval JSON on dataset/openfake_test, generator+real split holdout
- Pages updated: [[concepts/tribunal]], [[analyzers/custom_detector]], [[hot]]

## [2026-09-15] presigned-media-fix | Signed media URLs for a public endpoint; Caddy media block

- Source: prod `.env`, live `default_storage.url()` output on the server, storages 1.14.6 `url()`, `deploy/caddy.snippet`
- Pages created: [[fixes/presigned-media-public-endpoint]]
- Pages updated: [[hot]]

## [2026-09-04] tribunal-1.1-retrain | Ensemble named and versioned; custom_detector retrained on 2026 generators

- Source: `retrain_detector` run (CF backbone, openfake + hf), `fetch_openfake --start-row-group 6` + `dedupe_dataset` for a held-out test, eval JSONs (eval9 baseline, eval10 retrained, eval12/13 Tribunal 1.1 confirm), offline weight/rule simulation with the real `aggregate()`
- Summary: Tribunal identity (name, version, fingerprint) in API/status/landing; retrained member AUC 0.711 -> 0.993 held-out; lone-voter exception (share >= 50%, p >= 0.9) + weights CF 3.5 / custom 3.5 / ai 1.0; ensemble caught 23% -> 71% on unseen modern generators with 0 real photos called fake
- Commands added: `retrain_detector --extra-dir/--base-model`, `dedupe_dataset`, `fetch_openfake --start-row-group`, `make ship-retrained`
- Pages created: [[concepts/tribunal]]
- Pages updated: [[analyzers/custom_detector]] (rewritten), [[concepts/aggregation]], [[concepts/detector-evaluation]], [[analyzers/_index]], [[api/system-status]], [[frontend/routes]], [[fixes/audit-2026-08]], [[hot]]
- Headline: 130 seconds of fine-tuning on the right backbone did more than any threshold could - and the rule that let it count had to be shaped by the 5% of real photos the new model over-scores

## [2026-09-04] modern-generators-openfake | OpenFake eval, CF calibration, two face models unseeded

- Source: `ComplexDataLab/OpenFake` core/test parquet (150 real + 236 AI, 20 generators), eval JSONs, arXiv 2602.07814 benchmark for framing
- Summary: measured the ensemble on 2026 generators for the first time (41% of AI called authentic); found CF ranks fine (AUC 0.977) but is miscalibrated; shipped a holdout-validated piecewise-linear calibration; unseeded siglip (35% real-photo FP) and face_deepfake (AUC 0.181); ensemble AUC 0.808 -> 0.890, acc 0.627 -> 0.777, real->fake 0
- Commands added: `fetch_openfake` (memory-bounded parquet sampler), per-generator table in `eval_detectors`
- Pages updated: [[fixes/audit-2026-08]], [[analyzers/community-forensics]], [[analyzers/face-deepfake-detector]], [[analyzers/siglip-detector]], [[analyzers/_index]] (9 seeded), [[concepts/aggregation]], [[concepts/detector-evaluation]], [[hot]]
- Headline: a detector that separates 2022 output perfectly read 41% of 2026 output as real - and the fix was a threshold map with zero measured false positives, not a new model. flux.2 and sora-2 remain invisible.

## [2026-09-04] roster-drift-visibility | Analyzer roster drift check, probe, Makefile targets

- Source: `.env`, `docker-compose.yml`, `deploy/compose.prod.yml`, `Makefile`, `backend/api/system_views.py`, `backend/users/checks.py` (pattern)
- Summary: host-side `seed_analyzers` failure traced to compose hostnames in `.env`; added `analyzers/roster.py`, `analyzers.W001` system check, `/system/status` `analyzers` probe + StatusPage row, `seed_analyzers --check`, four Makefile targets; fixed seed never re-activating deactivated rows
- Pages updated: [[api/system-status]], [[analyzers/_index]], [[hot]]
- Headline: the roster only reconciles when the backend container restarts; every weight rebalance so far was invisible on a worker-only rebuild

## [2026-09-04] npr-real-implementation | Real NPR built, measured, benched; disagreement rule reweighted

- Source: `github.com/chuangchuangtan/NPR-DeepfakeDetection` (networks/resnet.py, data/datasets.py, HF demo app.py), authors' checkpoint `model_epoch_last_3090.pth`, `eval_detectors` on dataset/hf
- Summary: old `npr_detector` was a face ViT -> renamed `face_deepfake_detector`; real NPR implemented and verified against the authors' demo, then measured AUC 0.499 on diffusion output and left unseeded; aggregator disagreement now weight-share based
- Pages created: [[analyzers/face-deepfake-detector]]
- Pages updated: [[analyzers/npr-detector]] (rewritten), [[analyzers/_index]] (roster refresh, 12 analyzers), [[concepts/aggregation]], [[concepts/detector-evaluation]], [[concepts/detection-strategy-2026]], [[fixes/audit-2026-08]], [[services/celery-workers]], [[index]], [[hot]]
- Headline: a correctly implemented SOTA-2024 detector was worse than useless on 2026 diffusion imagery; the ensemble rule that let it do damage was the real defect

## [2026-08-19] system-audit | Full-stack audit: detection, security, reliability

- Source: live read of `backend/` (analyzers, content, common, provenance, config) + HF model configs + 2026 detection benchmark literature
- Summary: 11 correctness bugs and 3 security issues found and fixed; suite 33 failed/133 passed -> 301 passed
- Pages created: [[fixes/audit-2026-08]]
- Pages updated: [[concepts/aggregation]], [[hot]]
- Headline: aggregator silently zero-weighted `llm_vision`; EXIF sub-IFD never read so camera-signature was unreachable; video analysis broken on GPU; C2PA extraction dead since the c2pa-python 0.5 API change

## [2026-05-14] memory-bank-creation | Full ProofLayer wiki bootstrap

- Source: live read of `/Users/sevastyan0107/PycharmProjects/prooflayer/` (backend/, frontend/, docker-compose.yml, .env.example, models, services)
- Summary: First full wiki memory bank for the project
- Pages created (30+):
  - Index: [[index]], [[overview]], [[architecture]], [[hot]]
  - Services: [[services/backend]], [[services/celery-workers]], [[services/ollama]], [[services/postgres]], [[services/redis]], [[services/minio]], [[services/flower]], [[services/frontend]]
  - Analyzers: [[analyzers/_index]], [[analyzers/metadata]], [[analyzers/ela]], [[analyzers/ai-ensemble]], [[analyzers/llm-vision]], [[analyzers/video-frames]], [[analyzers/audio-spectrogram]], [[analyzers/llm-text]]
  - Models: [[models/Submission]], [[models/AnalysisResult]], [[models/AnalyzerConfig]], [[models/VerdictOverride]], [[models/KnownFakeHash]], [[models/User]]
  - Concepts: [[concepts/submission-pipeline]], [[concepts/aggregation]], [[concepts/verdict-thresholds]], [[concepts/skip-photo-check]], [[concepts/memory-budget]], [[concepts/detection-strategy-2026]]
  - Frontend: [[frontend/routes]], [[frontend/auth-flow]], [[frontend/shader-bg]], [[frontend/sidebar-layout]]
  - Infrastructure: [[infrastructure/docker-compose]], [[infrastructure/env-vars]]
  - API: [[api/endpoints]], [[api/system-status]]
  - Fixes: [[fixes/oom-sigkill]], [[fixes/organika-broken]], [[fixes/model-name-leak]], [[fixes/em-dash-purge]]
- Key insight: research synthesis from user (filed as [[concepts/detection-strategy-2026]]) identifies VLM-as-oracle as structurally wrong. 8-week roadmap to rebuild as calibrated ensemble.
