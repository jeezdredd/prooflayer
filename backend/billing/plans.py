from dataclasses import asdict, dataclass

from django.conf import settings

INTERVALS = ("month", "year")


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    audience: str
    monthly_usd: int | None
    yearly_usd: int | None
    uploads_per_month: int
    api_per_minute: int
    teacher_seats: int
    schools: int
    compare: bool
    embed: bool
    api: bool
    vlm: bool
    pdf: bool
    priority_support: bool
    sla: bool
    on_premise: bool
    self_serve: bool
    highlights: tuple[str, ...]

    @property
    def classroom(self) -> bool:
        return self.schools > 0


PLANS: dict[str, Plan] = {
    plan.key: plan
    for plan in (
        Plan(
            key="free", name="Free", audience="Try it on your own files.",
            monthly_usd=0, yearly_usd=0, uploads_per_month=50, api_per_minute=0, teacher_seats=0, schools=0,
            compare=False, embed=False, api=False, vlm=False, pdf=False,
            priority_support=False, sla=False, on_premise=False, self_serve=False,
            highlights=("50 checks a month", "Every Tribunal member", "Public feed and community votes"),
        ),
        Plan(
            key="pro", name="Pro", audience="Journalists, researchers, fact-checkers.",
            monthly_usd=12, yearly_usd=120, uploads_per_month=500, api_per_minute=120, teacher_seats=0, schools=0,
            compare=True, embed=True, api=True, vlm=True, pdf=True,
            priority_support=False, sla=False, on_premise=False, self_serve=True,
            highlights=("500 checks a month", "API keys and signed webhooks", "Compare, embed, PDF reports"),
        ),
        Plan(
            key="education", name="School", audience="Schools, colleges and lyceums.",
            monthly_usd=250, yearly_usd=2500, uploads_per_month=3000, api_per_minute=120, teacher_seats=30, schools=1,
            compare=True, embed=True, api=True, vlm=True, pdf=True,
            priority_support=True, sla=False, on_premise=False, self_serve=True,
            highlights=(
                "3 000 checks a month", "Your own school address in Classroom",
                "Up to 30 teachers, unlimited students", "PDF and DOCX essays",
            ),
        ),
        Plan(
            key="university", name="University", audience="Universities and faculties.",
            monthly_usd=500, yearly_usd=5000, uploads_per_month=15000, api_per_minute=300, teacher_seats=250, schools=10,
            compare=True, embed=True, api=True, vlm=True, pdf=True,
            priority_support=True, sla=False, on_premise=False, self_serve=True,
            highlights=(
                "15 000 checks a month", "Up to 10 faculties, each with its own address",
                "Up to 250 teachers, unlimited students", "Priority support",
            ),
        ),
        Plan(
            key="enterprise", name="Enterprise", audience="Newsrooms, platforms, trust and safety teams.",
            monthly_usd=None, yearly_usd=None, uploads_per_month=50000, api_per_minute=600, teacher_seats=0, schools=0,
            compare=True, embed=True, api=True, vlm=True, pdf=True,
            priority_support=True, sla=True, on_premise=True, self_serve=False,
            highlights=(
                "Volume and price agreed with you", "600 API requests a minute per key",
                "99.5% uptime SLA", "On-premise deployment on request",
            ),
        ),
    )
}

PAID_KEYS = tuple(k for k, p in PLANS.items() if p.monthly_usd)


def plan_for(tier: str) -> Plan:
    return PLANS.get(tier, PLANS["free"])


def price_id(plan_key: str, interval: str) -> str:
    return (getattr(settings, "PADDLE_PRICE_IDS", {}) or {}).get(f"{plan_key}:{interval}", "")


def tier_for_price(price: str) -> str | None:
    if not price:
        return None
    for key, value in (getattr(settings, "PADDLE_PRICE_IDS", {}) or {}).items():
        if value == price:
            return key.split(":", 1)[0]
    return None


def catalog() -> list[dict]:
    rows = []
    for plan in PLANS.values():
        row = asdict(plan)
        row["highlights"] = list(plan.highlights)
        row["classroom"] = plan.classroom
        row["checkout"] = {i: bool(plan.self_serve and price_id(plan.key, i)) for i in INTERVALS}
        rows.append(row)
    return rows
