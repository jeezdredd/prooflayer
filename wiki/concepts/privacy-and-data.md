---
type: concept
created: 2026-10-13
source: backend/content/retention.py, backend/users/views.py, backend/analyzers/training.py, backend/plagiarism/, frontend/src/pages/{PrivacyPage,TermsPage,RefundPage,DataProcessingPage,AccountPage}.tsx, frontend/src/legal.ts
---

# Privacy, retention and the legal pages

The legal pages (Terms, Privacy, Refund, Data Processing for schools at /data-processing) were
rewritten on 2026-10-13 against `.diag/legal_facts.md` (local, git-excluded facts sheet) and
then checked claim-by-claim against the code by reviewer agents. Rule: a page may only promise
what the code does. When the code changes, the pages must change with it.

Operator: Kazakhstan, server in Kazakhstan. Name / registration / address are empty in
`frontend/src/legal.ts` until the entity is registered; `operatorLine()` renders a neutral phrase.

What the code guarantees (and the pages say):
- Personal upload files deleted 90 days after upload (`content.retention`, daily beat task
  `purge-expired-personal-files`); verdicts stay; re-analysis of a purged file is refused.
- `/account`: training consent toggle and self-service deletion (`DELETE /auth/me/`, password).
  Refused while a paid subscription is active and not scheduled to cancel
  (`Subscription.cancel_scheduled` from Paddle's `scheduled_change`) and while the user owns a
  school. A deleting teacher's school classes pass to the school owner; classes outside a school
  are deleted with their work (never orphaned into personal uploads). Feedback and email logs go
  too.
- School owner can delete the school with all class work (`DELETE /classroom/orgs/<slug>/`).
- Training corpus `analyzers.TrainingSample`: copies only with opt-in consent, pseudonymous HMAC
  ref, deleted on withdrawal, never from class work; the retrainer reads only this table, so
  deletions and the 90-day purge do not shrink it.
- Originality repository holds class work only; personal uploads are compared but not stored.
- Class work cannot be made public.
- Backups 14 days.

Disclosed recipients: Cloudflare (traffic in transit), Paddle, Resend, Apple iCloud mail,
ip-api.com (over plain http), search engines via SearXNG / Brave / DuckDuckGo, Fact Check to
DuckDuckGo and Wikipedia, Discord if `DISCORD_WEBHOOK_URL` is set, Sentry if enabled.

Open items for a lawyer (from the reviewers): liability cap and indemnity, minors accepting terms
and the repository licence, parental consent by checkbox, transfer safeguards, sub-processor
change notice, breach notification to individuals, EU digital-content waiver vs 14-day refund,
refunds on plan changes. Engineering open items: ip-api over http (switch to a local GeoIP
database), Discord visit notices with full IPs (turn off for school sales), dormant TinEye /
Google Vision / Google Fact Check code paths (keep keys unset).

## Age, terms, objections (2026-10-13, after the owner's legal pack)

Owner decision: the service is NOT 18+. Registration stays simple (email, username, password,
accept terms, optional "I am 18 or older"). Age only gates material:
- `User.is_adult` (self-declared, `age_confirmed_at` keeps the last confirmation even if the
  user later unticks it), `common.age.can_view_sensitive(user)`.
- `Submission.is_sensitive` (author ticks it when publishing, staff admin action). Anonymous
  visitors and non-adults never get sensitive items: feed list/detail (404), widget, status view,
  similar submissions, compare, provenance list, PDF report matches
  (`content.sensitivity.for_viewer`, `provenance.visibility`). Adults get `is_sensitive` and the
  UI blurs (`SensitiveCover`). Non-adults cannot publish; unticking 18+ unpublishes everything.
  Cache-hit re-uploads copy `is_sensitive`. Report reason `adult_content` lets anyone flag it.
- Terms version: `settings.TERMS_VERSION` (mirrored in `frontend/src/legal.ts`; change both).
  `needs_terms` on the user; `TermsGate` blocks both app shells until `POST /auth/accept-terms/`.
- Kazakhstan Law 94-V art. 19-1: `content.VerdictObjection`, the author objects to a verdict,
  the class supervisor (or staff for personal uploads) answers; due in 3 business days; email to
  the teacher. Verdicts show "Probabilistic assessment. A person makes the decision."
- Cross-border minimisation: `Organization.web_search_enabled` (default off) gates the
  originality web search for class work; personal uploads still search.
Known gaps: no automatic NSFW detection yet (sensitive marking is manual or by report); the
websocket progress channel does not check sensitivity (low risk: no media); terms acceptance is a
UI gate, the API does not refuse calls from users with `needs_terms`.

## Objection copy (2026-10-16)

The submission detail returns `in_class` (true when `classroom_id` is set). The objection form only
mentions the teacher for class work; personal checks say "our reviewers" (they go to `ADMINS`). The
panel says "verdict", never "assessment", since personal checks have nothing to do with grading.

