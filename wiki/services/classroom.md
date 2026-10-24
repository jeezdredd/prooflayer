---
type: service
created: 2026-10-13
source: backend/classroom/, backend/common/documents.py, frontend/src/classroom/, frontend/src/pages/ClassroomDetailPage.tsx
---

# Classroom

The "Classroom dashboard" promised on the Education plan. A teacher checks student work with
Tribunal; students submit into the class.

## Model

- `classroom.Classroom`: owner (teacher), name, 8-char `join_code` from an unambiguous
  alphabet (no 0/O/1/I), `archived`. `rotate_code` / `create_for` retry on the unique collision.
- `classroom.Membership`: (classroom, user) unique.
- `Submission.classroom` and `Batch.classroom`, nullable, `SET_NULL`.
- `classroom.Organization`: a school. `name`, unique `slug` (3-40 chars, `[a-z0-9-]`, no hyphen at
  the ends, not in `RESERVED_SLUGS`), `owner` (PROTECT), 8-char `teacher_code`.
- `classroom.OrgMember`: (organization, user, role `admin` | `teacher`). The creator becomes admin.
- `Classroom.organization`: nullable. `Classroom.billing_owner` is the school's owner when set,
  else the teacher.

## Subdomain

Classroom lives on its own host, `classroom.prooflayer.cloud`, and each school gets
`classroom.prooflayer.cloud/<slug>`. Same SPA bundle: `frontend/src/appMode.ts` sets
`IS_CLASSROOM_APP` from the hostname (or `VITE_APP_MODE=classroom` locally), and `App.tsx` renders
`classroom/ClassroomApp.tsx` instead of the main routes. The main app's `/classroom/*` redirects to
the subdomain.

| route | page |
|---|---|
| `/` | hub: join a class, schools, enrolled classes, own classes without a school, create a school (Education) |
| `/:slug` | school page; public name for anonymous visitors, join forms for signed-in outsiders, class list (admin: all, teacher: own, student: enrolled), admin panel with teacher code, teachers, plan state |
| `/:slug/c/:id`, `/c/:id` | `ClassroomDetailPage` (teacher or student view) |
| `.../submit` | hand in work into that class (single, batch, ZIP, PDF/DOCX) |
| `/results/:id`, `/batches/:id` | reused result and batch pages, with classroom-aware back links |

- **Sign-in carries over.** The refresh cookie sits on `api.prooflayer.cloud` (SameSite=Lax), which
  is same-site with both frontends, so `classroom/useSilentSignIn.ts` calls `auth/refresh` once on
  load (one shared promise; the refresh token rotates, so StrictMode's double effect must not fire
  two refreshes) and then `auth/me`.
- `?next=` after login/register is honoured on both hosts, local paths only (`appMode.safeNext`).
- Prod settings append `CLASSROOM_URL` to `CORS_ALLOWED_ORIGINS` and its host to
  `WS_EXTRA_ORIGINS`; `config/asgi.py` validates WebSocket origins against `ALLOWED_HOSTS` plus
  that list (`content.ws_auth.ws_allowed_origins`), so live result updates work from the subdomain
  even when `ALLOWED_HOSTS` is a closed list.
- Caddy needs a `http://classroom.prooflayer.cloud` block proxying to the frontend (see
  `deploy/caddy.snippet`). Cloudflare's wildcard DNS already routes it.

## Rules

| who | can |
|---|---|
| Education plan or staff | create classes (`Subscription.can_classroom`, 402 otherwise) |
| any verified user | join by code (case-insensitive), leave |
| teacher | roster with per-student totals/flagged, stats, filtered submissions, CSV, rotate code, archive, take a student out |
| school admin | everything a teacher can, on every class of the school (`classroom.access.supervised_q` / `can_supervise`); teacher code, remove teachers |
| school teacher | create classes in the school under the school's plan, without a plan of their own |
| student | upload into the class (single, batch, PDF/DOCX), see only their own class submissions |

- **Billing:** a class upload is charged to the class's `billing_owner` (school owner, else the
  teacher). `billing.uploads_this_month(user)` = own personal uploads + uploads into the user's
  classes without a school + uploads into every class of schools the user owns. A student's class uploads do not count against the student.
- If the teacher's plan lapses, uploads into their classes return 403 rather than silently
  falling back to the students' own quota (`classroom.access.classroom_for_upload`).
- **Privacy:** the teacher can open a student's submission only if it was made into a class they
  supervise (`SubmissionViewSet.get_queryset` = `classroom.access.visible_submissions_q`: own OR
  class owner OR admin of the class's school; the WebSocket consumer uses the same rule). A fellow
  teacher of the same school sees nothing of another teacher's class. Personal uploads
  stay invisible. The teacher's own dashboard list (`action == "list"`) shows only the teacher's
  uploads. Delete and toggle-public stay author-only (403 for the teacher).

## Documents

PDF and DOCX are now first-class submissions (`ALLOWED_MIME_TYPES`). Extraction moved from
`factcheck/views.py` to `common/documents.py` (page cap 300, DOCX uncompressed cap 100 MB).
`text_classifier` reads PDF/DOCX through `read_text`, and `process_submission` stores
`metadata.document = {characters, words}`. libmagic often reports a python-docx/LibreOffice file
as `application/zip`; `content.validators._is_docx` accepts it as DOCX only when the name ends in
`.docx` **and** the package contains `word/document.xml`.

## UI

Sidebar 04 on the main app links out to the subdomain. Class page: teacher view (join code with copy/rotate, CSV, archive, stats strip, roster,
flagged-first submissions with student filter) or student view (own class submissions, Submit
work, Leave). Verify page shows a "Submit to" picker when the user belongs to any active class.

> [!warning] Text verdicts are indicative
> Since Tribunal 1.5 essays go through `text_classifier` (fine-tuned e5-small, see
> [[concepts/text-signals]]): about 2-4% of human essays get `suspicious`, none get `fake` on the
> held-out set. The teacher view still says a flag is a reason to talk to the student.

## Class radar (2026-10-14)

`GET /classroom/classrooms/<id>/radar/?days=60` (teacher or school admin, `can_supervise`), code in
`classroom/radar.py`, panel on the teacher view.

- **Shared skeleton.** For every pair of works by different students in the window (completed, up to
  200), sentence vectors from `plagiarism_sentence_vectors` are aligned: share of sentences whose best
  match in the other work has cosine >= 0.88 (averaged both ways) and the share of aligned matches
  that keep their order. A pair is reported when its share is an outlier for this class
  (>= mean + 2.5 sd over all pairs, at least 0.35; with fewer than 6 pairs it must reach 0.5) and at
  least 60% of matches are in order. The class baseline matters: one assignment topic makes every
  pair similar, a shared prompt or source makes one pair stand out. Pairs are merged into clusters.
- **Sudden jumps.** Per student, with at least two earlier works: readability grade (from
  `text_grade_fit`) 3+ grades above the median of earlier works, `text_classifier` ai_probability
  >= 0.75 when the earlier median was <= 0.3, or a `text_style` flag.

Read-only, computed on request, never changes a verdict.

## Assignment shadow (2026-10-14)

The teacher pastes an assignment (`POST /classroom/classrooms/<id>/shadows/`, up to 3 sets per class
per day, 1-12 answers, default 8). `classroom.tasks.build_shadow_set` (queue `ml`) asks the prod
Ollama model (`SHADOW_MODEL` or `OLLAMA_MODEL`) to answer it as students of four ages in four styles,
splits each answer into sentences and stores e5 vectors in `ShadowAnswer.vectors`. The language of
the prompt picks the template (detector, then Cyrillic vs Latin, French hints).

`text_shadow` (context member, queue `ml`) compares a class submission with every answer of the
class's sets from the last 120 days: share of the work's sentences with a match at cosine >= 0.9 and
how many of those keep the answer's order. Share >= 0.5 and order >= 0.7 gives `suspicious`, which
only sends the work to review; evidence carries the three closest sentence pairs. Thresholds are
conservative and not yet calibrated on real class data. On CPU Ollama (no ROCm yet) a set of 8 takes
several minutes.

## Student accounts (2026-10-14)

`classroom.access.is_student_only(user)`: a member of at least one class who owns no class, is not in
any school's staff (`OrgMember`), is not Django staff and has no paid plan. `/auth/me/` returns
`student_only`. Such an account may only hand work in to a class, read its own results and file an
objection. Refused with 403 `code: student_account`: uploads without a class, analyze-url, batches,
fact-check, the public feed, crowd votes, toggle-public and re-analyze. The main app sends a student to
the Classroom app (keeping `/results/<id>`), and the result page hides publish, re-run and voting.

## Teacher uploads for a student (2026-10-16)

`POST /content/submissions/` and `/content/batches/` take `student=<user id>` when the uploader
supervises the class (owner or school admin). The submission belongs to the student, so history, style
drift and roster counts work as if the student handed it in; `Submission.uploaded_by` (migration
content 0019) records the teacher and the class list shows it. Use case: work handed in on paper or by
email. Teacher view has a Check work button and a per-student shortcut.

## Status pulse (2026-10-16)

Classroom header shows eight service ticks and a one-line state; a click opens a card grouped for
teachers (checking work, files and reports, sign-in and email) with the Tribunal version. Non-student
accounts get a "← ProofLayer" link back to the main dashboard.

## Demo data (2026-10-14)

`manage.py seed_demo [--reset] [--no-wait]` reads `classroom/demo/demo_data.json`: Лицей №12 (8А,
history, ru: a strong student who is never flagged, an AI essay after three honest works, a humanizer
with homoglyphs and zero-width spaces, two students who rewrote the same AI answer, plus a shadow set)
and Northbridge University (PSY 201, en: invented references, a real APA list with format slips, an AI
essay). Works are backdated and analysed one by one through the real pipeline so personal baselines
see earlier work. Only `@demo.prooflayer.cloud` emails are accepted; passwords are printed once.
Run it in the `celery_worker` container (it needs the e5 model for the shadow answers).

**2026-10-17, every Classroom feature on show** (63 works). Seed also takes `teachers` (extra school
teachers as `OrgMember` TEACHER), class `teacher` (owner username), `archived`, `teacher_checks` (works
uploaded by the teacher with no student), work `batch` (one `Batch` per class + name) and objection
`days_ago` (backdates `created_at` and `due_at`, so an open one shows as overdue). Cases: Dmitry shows
style drift + grade fit + classifier on one essay; Ivan's open objection is overdue; batch
"Контрольная 8А · сканы" (3 works); an unsigned sheet checked by the teacher; second teacher Orlov with
9Б · Литература (Polina pastes two paragraphs of ru.wikipedia "Наташа Ростова" for the web originality
check, Timofey's AI essay uses fullwidth commas and a one-dot leader, Arina is honest); archived class
8А · 2024/25. Anna's three early works were rewritten: the earlier versions (written by Claude) were
caught as AI by t4, t6 and t7.

**2026-10-17 extension** (45 works). Works may carry `asset` (a file in `classroom/demo/assets/`, MIME from
the extension: pdf, docx, png, jpg), `uploaded_by_teacher` (sets `Submission.uploaded_by` to the class
teacher) and `objection` (`reason`, optional `response` + `decision` -> answered by the teacher, else open).
`scripts/build_demo_assets.py` rebuilds the PDF/DOCX files from the texts in the JSON (fpdf2, python-docx).
New cases, each checked locally against model t7 and the real analyzers before shipping:
- 8A: Kirill (3 own works + AI essay run through a humanizer-style rewrite, caught p=0.88, open objection);
  Sofia (3 own works + AI report DOCX "sent by email", uploaded by the teacher, with hidden white 1 pt text
  asking an AI grader to rate it human: `text_evasion` 0.97 -> fake); Dmitry's AI essay gets an answered
  objection (upheld after an oral talk); Anna's essay is a PDF with a real GOST bibliography (both books
  found); Olga hands in an "excursion photo" that is an AI image carrying a genuine Stable Diffusion XL
  watermark embedded with `invisible-watermark` (decoder: 48/48 bits, intact -> provenance proof).
- PSY 201: Jordan (3 reflections + a real gptinf humanizer output from the held-out set, caught p=0.86);
  Alex, Sam and Priya get two more reflections each so style and grade baselines (3 works) apply; Sam's
  report is a PDF.


## Class page for non-technical teachers (2026-10-17)

The owner read the 8А page as a teacher and could not follow it: the radar listed usernames with "81% совпадение" and
called a text "grade 20". Changes:
- `classroom/radar.py`: pair refs carry `filename` and `created_at`; jump reasons are dicts `{"kind": "readability", "now": band, "before": band}`,
  `{"kind": "ai"}`, `{"kind": "style"}` where `readability_band` maps the Oborneva/FK grade to primary (<=4), middle (<=9), senior (<=11), university.
  The frontend phrases them ("читается как текст уровня вуза, прежние работы были уровня 5–9 класса").
- Alignment thresholds measured on the demo essays: at 0.88 every pair of essays on the same assignment aligned at 0.75-0.8 with in-order 1.0
  (chronological topics), so the honest student landed in a cluster. At 0.92 only true copies (1.0) and the humanized AI essay (0.68) remain.
  `ALIGN_SIMILARITY` 0.92, `MIN_SHARE` 0.6, `STRONG_SHARE` 0.7.
- `ClassSubmissionSerializer.flags`: short keys for what fired, computed from prefetched `analysis_results` and the plagiarism report, ordered
  ai_text, ai_trace, trace_hidden, ai_image, hidden_text, tricks, shadow, copy, sources, age, style. The list shows them as chips.
- The class page lists open and answered objections, explains each section in one sentence, labels the stats tiles and list columns.
- Org page copy no longer promises Google/Bing/Yandex; it says Wikipedia, open academic catalogues and open web search.

Demo 9Б · Литература (teacher demo_orlov) mirrors every feature of 8А: shadow set "Нужно ли читать книги в эпоху интернета?",
Arina and Vera on the AI answer (skeleton pair, Arina objects "писали по одному плану"), Lev's humanizer-style Onegin essay with an
answered objection, Timofey's Pechorin with fullwidth punctuation and an overdue objection plus a teacher-uploaded DOCX with hidden
white text, Polina's honest PDF with real GOST references, her Wikipedia paste and an "excursion photo" with the SDXL watermark,
a batch of scanned "Гроза" answers and an unsigned sheet checked by the teacher. Honest short reflections stay under `MIN_TOKENS`.

## Class pages that act on what they show (2026-10-24)

The owner reviewed the demo again as a teacher: logins instead of names, counters that disagreed with the row chips,
"Вердикт изменён" that changed nothing, a radar percentage without sentences, English CSV headers. Changes:
- One attention rule, `classroom/attention.py` `attention_q()`: a completed work needs attention when its verdict is
  fake/likely_fake/suspicious/needs_review, or when any chip signal fires (flagged text check or `text_evasion`, a
  metadata AI trace, originality < 85), minus works a teacher cleared. The "Только с сигналом" filter, stats tiles,
  timeline, roster, batch summary, hub and school counts all use it. New chip `ai_media` for flagged audio and video.
  A row whose chips fire under an ok verdict reads "Есть на что посмотреть".
- Names: every person on class pages, the radar, objections, mails and school teachers goes through
  `common.names.display_name`. Class join, teacher join and school creation ask for "Имя и фамилия" when the account
  has none (`common.names.save_name`). A teacher's own upload with no student is `unattributed` ("Без ученика
  (проверка учителя)") and does not count as a student in the radar.
- Objections: decision `changed` clears the work (`content.objections.apply_decision`): `final_verdict` becomes
  `authentic`, the old verdict stays in `VerdictObjection.original_verdict` (migration content 0020) and a
  `VerdictOverride` is logged. Cleared work drops out of every count and chip list, and the CSV says so. The student
  gets an `objection_answer` mail; both objection mails link to `CLASSROOM_URL/results/<id>` for class work.
  Class rows carry `objection {status, decision, overdue, due_at, responded_at}` and `cleared`.
- Radar: each similar pair returns `k of n` matched sentences and up to 3 quoted sentence pairs (SentenceVector
  start/end into TextFingerprint text). Jumps no longer use readability bands: the vocabulary reason follows the
  `text_grade_fit` verdict (which already compares with the student's own history), the AI jump needs 3 earlier
  scored works. The header shows handed in vs compared sentence by sentence.
- CSV (`classroom/export.py`): for Excel, BOM, `;` and Russian headers when the viewer reads Russian, plain verdict
  and chip texts (same wording as the class page), matches %, objection status, no ids. Class batch CSVs use it too.
- Class batches: batch detail returns class rows with names and a flagged count, supervisors open students' class
  batches, the class page lists "Пакеты работ". SubmitPage no longer promises scans and names a batch by default.
- AI answers: plain heading and plurals, failures stored as codes (`llm_failed`, `no_answers`), copy says only
  work handed in after the answers is compared, each set lists the works that followed it.
- Confirmations before removing a student or teacher, issuing new codes, archiving and leaving a class.
- Demo: Anna's "Древняя_Русь_быт" (false 32% copy match with Kirill) has an answered `changed` objection; batches are
  "из электронного журнала"; Timofey's Pechorin carries 4 stray U+030D marks (`stray_marks` 4, t7 margin 5.62 -> 5.49);
  Jordan's humanized essay has 2 words with styled letters (`styled_letter_words`, NFKC leaves the model input as is).
  Still missing: a translation case and a TTS audio answer.
