from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db.models import Count
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from analyzers import auto_retrain
from analyzers.ensemble import ensemble_info
from analyzers.models import AnalyzerConfig, RetrainRun, TrainingSample
from analyzers.retrain_report import holdout_rows, status_variant
from analyzers.roster import roster_drift
from api.models import Feedback
from billing.models import Subscription
from classroom.models import Classroom, Membership, Organization
from content.models import Submission, VerdictObjection
from content.views import REVIEW_VERDICTS
from users.models import User

STUCK_AFTER = timedelta(minutes=10)
RECENT_FEEDBACK = 5
FEEDBACK_PREVIEW = 140

VERDICT_ORDER: tuple[tuple[str, str, str], ...] = (
    ("authentic", "Authentic", "success"),
    ("likely_authentic", "Likely authentic", "success"),
    ("inconclusive", "Inconclusive", ""),
    ("needs_review", "Needs review", "info"),
    ("suspicious", "Suspicious", "warning"),
    ("likely_fake", "Likely AI", "danger"),
    ("fake", "AI", "danger"),
)

PAID_STATUSES = (Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE)


def is_superuser(request: HttpRequest) -> bool:
    return bool(request.user.is_active and request.user.is_superuser)


def review_queue_count() -> int:
    return Submission.objects.filter(status=Submission.Status.COMPLETED, final_verdict__in=REVIEW_VERDICTS).count()


def open_objections_count() -> int:
    return VerdictObjection.objects.filter(status=VerdictObjection.Status.OPEN).count()


def review_queue_badge(request: HttpRequest) -> str:
    return _badge(review_queue_count())


def open_objections_badge(request: HttpRequest) -> str:
    return _badge(open_objections_count())


def _badge(count: int) -> str:
    return str(count) if count else ""


def dashboard_callback(request: HttpRequest, context: dict[str, Any]) -> dict[str, Any]:
    if is_superuser(request):
        context["dashboard"] = build_dashboard()
    return context


def build_dashboard(now: datetime | None = None) -> dict[str, Any]:
    now = now or timezone.now()
    return {
        "submissions": _submissions(now),
        "verdicts": _verdict_mix(now),
        "queue": _queue(now),
        "tribunal": _tribunal(),
        "retrain": _retrain(),
        "training": _training(now),
        "classroom": _classroom(),
        "users": _users(now),
        "billing": _billing(),
        "feedback": _feedback(),
        "links": _links(),
    }


def _submissions(now: datetime) -> dict[str, int]:
    start_of_day = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "today": Submission.objects.filter(created_at__gte=start_of_day).count(),
        "week": Submission.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
        "total": Submission.objects.count(),
    }


def _verdict_mix(now: datetime) -> dict[str, Any]:
    counts = dict(
        Submission.objects.filter(status=Submission.Status.COMPLETED, created_at__gte=now - timedelta(days=7))
        .exclude(final_verdict="")
        .values_list("final_verdict")
        .annotate(count=Count("id"))
    )
    total = sum(counts.values())
    known = {key for key, _, _ in VERDICT_ORDER}
    rows = [(key, label, variant, counts.get(key, 0)) for key, label, variant in VERDICT_ORDER]
    rows += [
        (key, key.replace("_", " ").capitalize(), "", count)
        for key, count in sorted(counts.items())
        if key not in known
    ]
    return {
        "total": total,
        "rows": [
            _verdict_row(key, label, variant, count, total)
            for key, label, variant, count in rows
        ],
    }


def _verdict_row(key: str, label: str, variant: str, count: int, total: int) -> dict[str, Any]:
    percent = round(count * 100 / total) if total else 0
    return {
        "key": key,
        "label": label,
        "variant": variant,
        "count": count,
        "percent": percent,
        "summary": f"{count} ({percent}%)",
    }


def _queue(now: datetime) -> dict[str, int]:
    week = now - timedelta(days=7)
    processing = Submission.objects.filter(status=Submission.Status.PROCESSING)
    open_objections = VerdictObjection.objects.filter(status=VerdictObjection.Status.OPEN)
    return {
        "pending": Submission.objects.filter(status=Submission.Status.PENDING).count(),
        "processing": processing.count(),
        "stuck": processing.filter(updated_at__lt=now - STUCK_AFTER).count(),
        "failed_week": Submission.objects.filter(status=Submission.Status.FAILED, created_at__gte=week).count(),
        "review": review_queue_count(),
        "objections_open": open_objections.count(),
        "objections_overdue": open_objections.filter(due_at__lt=now).count(),
    }


def _tribunal() -> dict[str, Any]:
    info = ensemble_info()
    roster = roster_drift()
    total = AnalyzerConfig.objects.count()
    return {
        "label": info["label"],
        "version": info["version"],
        "fingerprint": info["fingerprint"],
        "active": AnalyzerConfig.objects.filter(is_active=True).count(),
        "total": total,
        "expected": roster["expected"],
        "configured": f"{total} / {roster['expected']}",
        "in_sync": roster["in_sync"],
    }


def _retrain() -> dict[str, Any] | None:
    run = RetrainRun.objects.select_related("triggered_by").first()
    if run is None:
        return None
    metrics = run.metrics or {}
    return {
        "id": str(run.id),
        "status": run.status,
        "variant": status_variant(run.status),
        "reason": run.error,
        "samples_used": run.samples_used,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "triggered_by": run.triggered_by.email if run.triggered_by else "schedule",
        "holdout": holdout_rows(metrics),
        "problems": metrics.get("problems") or [],
        "url": reverse("admin:analyzers_retrainrun_change", args=[run.id]),
    }


def _training(now: datetime) -> dict[str, Any]:
    last_success = (
        RetrainRun.objects.filter(media_type="image", status=RetrainRun.Status.SUCCESS).order_by("-finished_at").first()
    )
    since = last_success.finished_at if last_success and last_success.finished_at else now - timedelta(days=365)
    return {
        "pool": auto_retrain.image_count(auto_retrain.POOL),
        "calibration": auto_retrain.image_count(auto_retrain.CALIBRATION),
        "holdout": auto_retrain.image_count(auto_retrain.HOLDOUT),
        "new_samples": TrainingSample.objects.filter(media_type="image", created_at__gte=since).count(),
        "total_samples": TrainingSample.objects.count(),
        "needed": getattr(settings, "RETRAIN_MIN_NEW_SAMPLES", 50),
        "rollback_available": auto_retrain.PREVIOUS.exists(),
    }


def _classroom() -> dict[str, int]:
    return {
        "organizations": Organization.objects.count(),
        "classrooms": Classroom.objects.filter(archived=False).count(),
        "students": Membership.objects.values("user").distinct().count(),
    }


def _users(now: datetime) -> dict[str, int]:
    return {
        "total": User.objects.count(),
        "week": User.objects.filter(date_joined__gte=now - timedelta(days=7)).count(),
    }


def _billing() -> dict[str, Any]:
    counts = dict(
        Subscription.objects.exclude(tier=Subscription.Tier.FREE)
        .filter(status__in=PAID_STATUSES)
        .values_list("tier")
        .annotate(count=Count("id"))
    )
    tiers = [
        {"tier": value, "label": label, "count": counts.get(value, 0)}
        for value, label in Subscription.Tier.choices
        if value != Subscription.Tier.FREE
    ]
    past_due = (
        Subscription.objects.filter(status=Subscription.Status.PAST_DUE).exclude(tier=Subscription.Tier.FREE).count()
    )
    return {"tiers": tiers, "paid": sum(counts.values()), "past_due": past_due}


def _feedback() -> list[dict[str, Any]]:
    rows = Feedback.objects.select_related("user").order_by("-created_at")[:RECENT_FEEDBACK]
    return [
        {
            "category": item.get_category_display(),
            "message": _preview(item.message),
            "who": item.user.email if item.user else (item.contact_email or "anonymous"),
            "created_at": item.created_at,
            "url": reverse("admin:api_feedback_change", args=[item.id]),
        }
        for item in rows
    ]


def _preview(text: str) -> str:
    return text if len(text) <= FEEDBACK_PREVIEW else text[:FEEDBACK_PREVIEW].rstrip() + "..."


def _links() -> dict[str, str]:
    submissions = reverse("admin:content_submission_changelist")
    review = ",".join(REVIEW_VERDICTS)
    return {
        "submissions": submissions,
        "processing": f"{submissions}?status__exact=processing",
        "failed": f"{submissions}?status__exact=failed",
        "review": f"{submissions}?status__exact=completed&final_verdict__in={review}",
        "objections": reverse("admin:content_verdictobjection_changelist") + "?status__exact=open",
        "analyzers": reverse("admin:analyzers_analyzerconfig_changelist"),
        "retrain": reverse("admin:analyzers_retrainrun_changelist"),
        "training_samples": reverse("admin:analyzers_trainingsample_changelist"),
        "organizations": reverse("admin:classroom_organization_changelist"),
        "classrooms": reverse("admin:classroom_classroom_changelist"),
        "subscriptions": reverse("admin:billing_subscription_changelist"),
        "feedback": reverse("admin:api_feedback_changelist"),
        "users": reverse("admin:users_user_changelist"),
    }
