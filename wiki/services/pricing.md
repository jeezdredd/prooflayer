---
type: service
created: 2026-10-13
source: backend/billing/plans.py, backend/billing/views.py, frontend/src/pages/PricingPage.tsx
---

# Pricing

One catalog, `billing/plans.py:PLANS`. `Subscription` flags and limits, the API-key rate,
Classroom seat and school limits, the `/billing/plans/` endpoint and the pricing page all read it.
Yearly is about 17% off and is shown per month with the struck-through monthly-billing total (2026-10-16).

| plan (tier value) | month | year | checks / mo | API / min / key | classroom | teachers |
|---|---|---|---|---|---|---|
| Free (`free`) | 0 | 0 | 50 | none | no | - |
| Pro (`pro`) | $11.99 | $9.99 / mo | 500 | 120 | no | - |
| School (`education`) | $249.99 | $207.99 / mo | 3 000 | 120 | 1 address | 30 |
| University (`university`) | $499.99 | $415.99 / mo | 15 000 | 300 | 10 addresses (faculties) | 250 |
| Enterprise (`enterprise`) | contact sales | - | 50 000 default | 600 | no | - |

2026-10-16: charm prices (.99), cents in small superscript on the page. The embed widget is gone from every plan.

2026-10-13: owner raised School to $250 and University to $500 (first draft was $49 / $149) and
made Enterprise sales-led (`monthly_usd=None`, `self_serve=False`, page shows "Custom" and
"Talk to sales"). Enterprise can still be billed through Paddle if `PADDLE_PRICE_ENTERPRISE_*`
ids are set and the subscription is created by hand; the webhook maps it. Students are never
charged.

- **Tier value `education` is the School plan** (kept for existing rows); `university` is new
  (migration `billing/0003`).
- **Seats** count distinct teachers (`OrgMember`) across all schools of one owner; joining past
  the limit is 403. Creating a school past `Plan.schools` is 402. Staff owners bypass both.
- **Checkout** `POST /billing/checkout/ {plan, interval}` picks `PADDLE_PRICE_IDS["plan:interval"]`
  (env `PADDLE_PRICE_<PLAN>_<MONTH|YEAR>`; `PADDLE_PRO_PRICE_ID` still fills `pro:month`). No
  price configured gives 409 `contact_sales` and the page falls back to `sales@prooflayer.cloud`;
  an active paid subscription gives 409 `manage_in_portal`.
- **Webhook** sets the tier from the subscription's price id (`tier_for_price`). It used to force
  `pro` for every subscription. An unknown price keeps the current tier and logs a warning.
- **API rate** `ApiKeyRateThrottle` uses `plan.api_per_minute` of the key owner.

To go live: create the eight prices in Paddle, put their ids in the server `.env`, redeploy.
