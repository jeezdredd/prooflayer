---
type: service
created: 2026-10-13
source: backend/classroom/, backend/common/documents.py, frontend/src/pages/Classroom*.tsx
---

# Classroom

The "Classroom dashboard" promised on the Education plan. A teacher checks student work with
Tribunal; students submit into the class.

## Model

- `classroom.Classroom`: owner (teacher), name, 8-char `join_code` from an unambiguous
  alphabet (no 0/O/1/I), `archived`. `rotate_code` / `create_for` retry on the unique collision.
- `classroom.Membership`: (classroom, user) unique.
- `Submission.classroom` and `Batch.classroom`, nullable, `SET_NULL`.

## Rules

| who | can |
|---|---|
| Education plan or staff | create classes (`Subscription.can_classroom`, 402 otherwise) |
| any verified user | join by code (case-insensitive), leave |
| teacher | roster with per-student totals/flagged, stats, filtered submissions, CSV, rotate code, archive, take a student out |
| student | upload into the class (single, batch, PDF/DOCX), see only their own class submissions |

- **Billing:** a class upload is charged to the **teacher's** quota.
  `billing.uploads_this_month(user)` = own personal uploads + every upload into classes the user
  owns. A student's class uploads do not count against the student.
- If the teacher's plan lapses, uploads into their classes return 403 rather than silently
  falling back to the students' own quota (`classroom.access.classroom_for_upload`).
- **Privacy:** the teacher can open a student's submission only if it was made into the
  teacher's class (`SubmissionViewSet.get_queryset` = own OR `classroom__owner`). Personal uploads
  stay invisible. The teacher's own dashboard list (`action == "list"`) shows only the teacher's
  uploads. Delete and toggle-public stay author-only (403 for the teacher).

## Documents

PDF and DOCX are now first-class submissions (`ALLOWED_MIME_TYPES`). Extraction moved from
`factcheck/views.py` to `common/documents.py` (page cap 300, DOCX uncompressed cap 100 MB).
`llm_text` reads PDF/DOCX through `read_text`, and `process_submission` stores
`metadata.document = {characters, words}`. libmagic often reports a python-docx/LibreOffice file
as `application/zip`; `content.validators._is_docx` accepts it as DOCX only when the name ends in
`.docx` **and** the package contains `word/document.xml`.

## UI

`/classroom` (sidebar 04): join by code, create (Education), Teaching / Enrolled lists.
`/classroom/:id`: teacher view (join code with copy/rotate, CSV, archive, stats strip, roster,
flagged-first submissions with student filter) or student view (own class submissions, Submit
work, Leave). Verify page shows a "Submit to" picker when the user belongs to any active class.

> [!warning] Text detection is the weak link
> Essays go through `llm_text`, a prompted 3B model. The teacher view says verdicts on text are
> indicative only. A real text detector is the open item that matters most for this feature.
