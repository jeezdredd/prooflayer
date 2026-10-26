---
type: service
created: 2026-05-18
source: backend/users/
---

# Auth + Email Verification

JWT auth via `rest_framework_simplejwt`. Email verification via signed token + Resend HTTP API (django-anymail).

## Flow

1. `POST /api/v1/auth/register/` -> creates `User(is_verified=False)` + dispatches `send_verification_email.delay(user.id)` -> returns JWT pair (user logged in immediately, banner nags them to verify).
2. Celery task creates [[EmailVerificationToken]] (48h expiry, `secrets.token_urlsafe(32)`) and sends email with link `${FRONTEND_URL}/verify-email?token=<token>`.
3. Frontend `VerifyEmailPage` (`frontend/src/pages/EmailLinkPages.tsx`, shared with `ConfirmEmailPage`) reads `?token=` -> `POST /api/v1/auth/verify-email/ {token}`. Endpoint validates token, flips `user.is_verified = True`, marks token used. The page posts each token once (module-level promise per token), so StrictMode and the `setUser` re-render no longer send a second request that came back 410 and showed a false failure to signed-in users.
4. Unverified users see `EmailVerifyBanner` in [[Layout]]. Button -> `POST /auth/resend-verification/` (auth required).

## Models

`users.EmailVerificationToken`:
- `user` FK -> User
- `token` char(64) unique, default `_gen_token` (token_urlsafe(32))
- `created_at`, `expires_at` (default +48h), `used_at`
- `is_valid()` -> `used_at is None and now < expires_at`

Superusers auto-verified (`UserManager.create_superuser` sets `is_verified=True`).

## Endpoints

| Method | Path | Auth | Body |
|--------|------|------|------|
| POST | `/api/v1/auth/verify-email/` | Anon | `{token}` |
| POST | `/api/v1/auth/resend-verification/` | JWT | (none) |
| POST | `/api/v1/auth/email/change/` | JWT only | `{new_email, password}` |
| DELETE | `/api/v1/auth/email/change/` | JWT only | (none) |
| POST | `/api/v1/auth/email/change/resend/` | JWT only | (none) |
| POST | `/api/v1/auth/email/change/confirm/` | Anon | `{token}` |

Response codes (verify): 200 verified, 400 missing/already-verified, 404 invalid token, 410 expired/used.

## Email change (2026-10-26)

Owner request: "add the ability to change the email in the profile and ask for re-verification on change".
The address never changes until the new one is proven.

`users.EmailChangeToken` (migration `0008_email_change_token`, table `email_change_tokens`): `user`, `new_email`,
`token` (`secrets.token_urlsafe(32)`), `created_at`, `expires_at` (+24 h, `EMAIL_CHANGE_HOURS`), `used_at`,
`cancelled_at`. Partial unique constraint `one_open_email_change_per_user` (one row per user with `used_at` and
`cancelled_at` both null); `pending()` = open and not expired, `EmailChangeToken.pending_for(user)`.

Flow:
1. `POST /auth/email/change/` (`EmailChangeView`, throttle scope `email_change` 5/hour per user, counted on every
   POST including wrong passwords). Order of checks: demo account -> 403 `demo_account`; password -> 403
   `wrong_password`; address normalised (`normalize_email`, trimmed) and validated, demo domain refused -> 400
   `invalid_email`; same address in any case -> 400 `same_email`; any other `User.email__iexact` -> 400
   `email_taken`. Then, with the user row locked, older open tokens are cancelled and a new one created. Returns 202
   `{pending_email, delivery}`.
2. Mails: `email_change_confirm` to the NEW address with `{FRONTEND_URL}/confirm-email?token=...`;
   `email_change_notice` to the OLD address with the new one masked (`n***@domain`) and a "Reset password" button
   (a password reset cancels open change requests). Sent to the old address whether or not it was ever verified.
3. `POST /auth/email/change/confirm/` (`EmailChangeConfirmView`, AllowAny, no authentication, so the link works
   logged out or on another device). In one transaction it locks the user row first and then the token row (same
   order as the request view, so the two never deadlock), then: unknown -> 404 `invalid`, used -> 410 `used`,
   cancelled -> 410 `cancelled`, expired -> 410 `expired`, demo -> 403 `demo_account`, address taken meanwhile
   (case-insensitive re-check) -> 409 `email_taken`; an `IntegrityError` from the unique `email` column is also
   reported as 409 `email_taken`. On success: `email = new_email`, `is_verified = True`, token used, other open
   change tokens cancelled, unused `EmailVerificationToken`s marked used, `email_changed` mail to the old address.
4. `DELETE /auth/email/change/` cancels; `POST /auth/email/change/resend/` (scope `email_change_resend` 5/hour)
   resends the same link and moves its expiry to now + 24 h; 404 `no_pending` when nothing is waiting.

Old password-reset links die on the change: Django's `default_token_generator` hashes the email field
(tested in `users/tests/test_email_change.py::TestConfirm::test_old_password_reset_links_stop_working`). Sign-in
uses the new address at once (login matches the stored address exactly, as at registration).

The email change endpoints accept JWT only (`authentication_classes = (JWTAuthentication,)`), so an API key can
never start or cancel a change. `UserSerializer` (`/auth/me/`) exposes `pending_email` (or null) and `is_demo`.

Frontend: `AccountPage` "Email" block shows the address with confirmed / not confirmed, a "Change email" form (new
address + current password, errors mapped from the codes, 429 -> "wait an hour"), then a pending box ("We sent a
link to {email}. Your address changes when you open it.") with "Send again" and "Cancel the change"; it refetches
`/auth/me/` on window focus while a change is pending. `ConfirmEmailPage` (`/confirm-email` on both hosts) posts
the token once, refreshes the signed-in user (`auth/sessionSync.refreshSignedInUser`) and offers "Open your account"
or "Sign in". Staff can preview and test-send the three new mails from the Email row on the status page
(`mail_samples.KINDS`).

## Demo account locks (2026-10-26)

`common/demo.py` holds `DEMO_DOMAIN` (`demo.prooflayer.cloud`, also used by `seed_demo`), `is_demo_email`,
`is_demo`, `refuse_demo(user)` (403 `{"detail": "This is a shared demo account, so this is turned off.", "code":
"demo_account"}`), `DemoLockedWritesMixin` (refuses every non-GET for demo users) and `refuse_demo_mixing(owner,
user)`. The demo passwords are public, so these are locked for `@demo.prooflayer.cloud` accounts:

- email change request, resend and confirm; account deletion (`MeView.delete`); password reset request and confirm
- API keys: create, rename, revoke (listing still works)
- billing: checkout and customer portal
- school: delete the school, remove a teacher, issue a new teacher code
- joins never mix demo and real accounts: a real account cannot join a demo school as teacher or a demo class as
  student (403 `demo_school`, "This is a demo school. Only its demo accounts can join it."), a demo account cannot
  join a real school or class (403 `demo_account`). This keeps visitors from using the demo school's Education plan
  for their own classes and keeps real pupils' work out of a school whose admin password is public.

Not locked on purpose: profile fields (username, language, age, training consent, product updates), the school's
web search switch, class-level actions (rename, archive, new class code, remove a pupil), uploads and objections:
visitors are meant to try them, and `seed_demo --reset` restores the demo.

The account page shows a short note instead of the email form and the delete form for demo accounts; pricing shows
"payments are turned off".

## Settings (env-driven)

```python
EMAIL_HOST          # smtp.resend.com
EMAIL_PORT          # 587
EMAIL_USE_TLS       # true
EMAIL_HOST_USER     # resend  (literal string "resend")
EMAIL_HOST_PASSWORD # re_xxxxxxxxxxxxxxxxxxxx  (Resend API key)
DEFAULT_FROM_EMAIL  # "ProofLayer <noreply@prooflayer.cloud>"
FRONTEND_URL        # https://prooflayer.cloud
```

When `EMAIL_HOST` is empty, `EMAIL_BACKEND` falls back to `console.EmailBackend` (dev prints to stdout, never tries SMTP).

## Resend HTTP API setup

Production uses [Resend](https://resend.com) HTTP API via `django-anymail[resend]`. Uses HTTP, not SMTP, so **no MX records required**. MX records on `prooflayer.cloud` belong to Cloudflare Email Routing (for receiving at `hello@prooflayer.cloud`).

- `RESEND_API_KEY` = Resend API key (`re_...`)
- `EMAIL_BACKEND` = `anymail.backends.resend.EmailBackend` (set automatically when key present)
- Can send FROM any address on verified domain: `noreply@prooflayer.cloud`, `hello@prooflayer.cloud`, etc.
- `anymail` app added to `INSTALLED_APPS` dynamically when `RESEND_API_KEY` set.

## Verification gating

Backend `users.permissions.IsVerifiedUser` (`backend/users/permissions.py`):
```python
class IsVerifiedUser(BasePermission):
    message = "Email verification required."
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "is_verified", False))
```

Staff/superuser users bypass `IsVerifiedUser` entirely (always return True).

Gated endpoints (require `is_verified=True`, return 403 otherwise):
- `POST /api/v1/content/submissions/` (upload) - `SubmissionViewSet.get_permissions` swaps on action
- `POST /api/v1/factcheck/check/` - `FactCheckView`
- `POST /api/v1/crowdsource/vote/` - `VoteCreateView`
- `POST /api/v1/reports/` - `ReportCreateView`

Read endpoints (`/auth/me`, list/retrieve submissions, status) stay on `IsAuthenticated` / `AllowAny`.

Frontend `ProtectedRoute requireVerified`: wraps gated routes in `App.tsx`. Unverified user sees [[VerifyGate]] panel instead of `<Navigate>` redirect. Verified users hit page as normal.

Wrapped: `/upload`, `/compare`, `/review`, `/factcheck`.
Open to authed-but-unverified: `/dashboard`, `/community-fakes`, `/results/:id`, `/status`.

## Cookie-based refresh token (security)

Refresh token sits in **httpOnly Secure SameSite=Lax cookie**, not localStorage. XSS cannot exfiltrate it. Access token (15 min TTL) sits in `sessionStorage` + in-memory zustand.

Cookie attrs:
| Attr | Value | Why |
|------|-------|-----|
| `name` | `prooflayer_refresh` | scoped name |
| `httpOnly` | `True` | JS cannot read |
| `secure` | `True` (prod) | HTTPS only |
| `samesite` | `Lax` | blocks CSRF on POST cross-site, allows top-level GET nav |
| `path` | `/api/v1/auth/` | only auth endpoints see it |
| `max_age` | 7 days | matches `REFRESH_TOKEN_LIFETIME` |

Backend views (`backend/users/views.py`):
- `CookieTokenObtainPairView` - login, moves `refresh` from JSON body into Set-Cookie
- `CookieTokenRefreshView` - reads refresh from cookie, returns new access + rotates cookie
- `LogoutView` - blacklists refresh, clears cookie
- `RegisterView` - sets cookie on signup

Frontend (`frontend/src/api/client.ts`):
- `withCredentials: true` on every axios call
- Access token in `sessionStorage` (`access` key) + zustand memory
- 401 interceptor calls `POST /auth/refresh/` (cookie auto-sent), retries

JWT blacklist app enabled (`rest_framework_simplejwt.token_blacklist`). `BLACKLIST_AFTER_ROTATION=True` means stolen old refresh tokens cannot be reused after rotation; logout actively blacklists.

### Env vars

```
REFRESH_COOKIE_DOMAIN=  # empty = host-only (recommended)
REFRESH_COOKIE_SECURE=true  # false in dev (localhost http)
REFRESH_COOKIE_SAMESITE=Lax  # Strict breaks email-link nav
```

Dev override: `dev.py` sets `REFRESH_COOKIE_SECURE=False` + `CORS_ALLOW_CREDENTIALS=True`.

### CORS

`CORS_ALLOW_CREDENTIALS=True` required so browsers attach cookie cross-origin (`prooflayer.cloud` -> `api.prooflayer.cloud`). Frontend axios must also set `withCredentials: true`.

## Email robustness + audit trail (2026-06-21)

All outbound mail flows through one choke point `backend/users/emails.py:deliver(msg, kind, user=None)`: it sends, then writes a best-effort `EmailLog` row (status `sent` | `console` | `failed`) and re-raises real failures so `send_verification_email`'s autoretry still fires. The log write is wrapped in try/except so it can never break the send (also survives the migration race where the worker boots before the `email_logs` table exists). `send_verification_email` (reuses a still-valid token instead of minting a new one per retry) and the retrain-notify email both route through it; the retrain caller swallows the re-raise so a finished retrain is never re-run.

The trap this fixes: with no `RESEND_API_KEY`, `base.py` falls back to the console backend and `msg.send()` "succeeds" silently - no email, no error. `send_verification_email` runs on the (ROCm) worker, which reads its env from `env_file: .env`, so a missing key there breaks delivery with zero signal.

Visibility now:
- `EMAIL_CONFIGURED = bool(RESEND_API_KEY)` in settings; a Django system check (`users.W001`) warns loudly on every `manage.py`/deploy when prod is unconfigured (warning, never blocks boot).
- `/api/v1/system/status/` `email` probe: `skip` in dev console, `down` in prod when unconfigured OR when recent `console`/`failed` EmailLog rows exist (catches worker-side drift the API process cannot see directly). PII-free - exposes only status/backend/from_email/recent_failures.
- `EmailLog` admin (read-only) lists every send. Register + resend responses carry `delivery: "email" | "console"` so VerifyGate shows an honest "not configured" message instead of a false "sent".
- `python manage.py send_test_email <addr>` - ops smoke test through the configured backend.

Three email modes (selected in `base.py`, exposed as `EMAIL_MODE`, which drives the EmailLog `backend` label + the status probe):
- `resend` - `RESEND_API_KEY` set -> anymail Resend HTTP backend.
- `smtp` - no Resend key but `EMAIL_HOST` set -> Django SMTP backend (`EMAIL_PORT`/`EMAIL_USE_TLS`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`). Homelab uses this (Resend over SMTP: `smtp.resend.com`, user `resend`, password = the `re_` key).
- `console` - neither set -> not delivered (the silent trap the audit trail surfaces).

`EMAIL_CONFIGURED = EMAIL_MODE != "console"`. Required keys for real delivery: either `RESEND_API_KEY`, or `EMAIL_HOST` + SMTP creds; plus `DEFAULT_FROM_EMAIL`, `FRONTEND_URL`, and a verified sender domain.

## See also

- [[users-model]]
- [[infrastructure/env-vars]]
- [[services/celery-workers]]
- [[services/gpu-rocm]]
