---
type: service
created: 2026-05-18
source: backend/users/
---

# Auth + Email Verification

JWT auth via `rest_framework_simplejwt`. Email verification via signed token + Resend SMTP.

## Flow

1. `POST /api/v1/auth/register/` -> creates `User(is_verified=False)` + dispatches `send_verification_email.delay(user.id)` -> returns JWT pair (user logged in immediately, banner nags them to verify).
2. Celery task creates [[EmailVerificationToken]] (48h expiry, `secrets.token_urlsafe(32)`) and sends email with link `${FRONTEND_URL}/verify-email?token=<token>`.
3. Frontend `VerifyEmailPage` reads `?token=` -> `POST /api/v1/auth/verify-email/ {token}`. Endpoint validates token, flips `user.is_verified = True`, marks token used.
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

Response codes: 200 verified, 400 missing/already-verified, 404 invalid token, 410 expired/used.

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

Gated endpoints (require `is_verified=True`, return 403 otherwise):
- `POST /api/v1/content/submissions/` (upload) - `SubmissionViewSet.get_permissions` swaps on action
- `POST /api/v1/factcheck/` - `FactCheckView`
- `POST /api/v1/crowdsource/vote/` - `VoteCreateView`
- `POST /api/v1/reports/` - `ReportCreateView`

Read endpoints (`/auth/me`, list/retrieve submissions, status, embed widget) stay on `IsAuthenticated` / `AllowAny`.

Frontend `ProtectedRoute requireVerified`: wraps gated routes in `App.tsx`. Unverified user sees [[VerifyGate]] panel instead of `<Navigate>` redirect. Verified users hit page as normal.

Wrapped: `/upload`, `/compare`, `/review`, `/factcheck`.
Open to authed-but-unverified: `/dashboard`, `/community-fakes`, `/embed`, `/results/:id`, `/status`.

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

## See also

- [[users-model]]
- [[infrastructure/env-vars]]
- [[services/celery-workers]]
