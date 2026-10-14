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
