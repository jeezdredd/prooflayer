import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .plans import Plan, plan_for


class Subscription(models.Model):
    class Tier(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        EDUCATION = "education", "Education: School"
        UNIVERSITY = "university", "Education: University"
        ENTERPRISE = "enterprise", "Enterprise"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELLED = "cancelled", "Cancelled"
        TRIALING = "trialing", "Trialing"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.FREE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    paddle_customer_id = models.CharField(max_length=64, blank=True, db_index=True)
    paddle_subscription_id = models.CharField(max_length=64, blank=True, db_index=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"

    def __str__(self):
        return f"{self.user.email} - {self.tier}"

    @property
    def is_active(self) -> bool:
        return self.status in (self.Status.ACTIVE, self.Status.TRIALING)

    @property
    def plan(self) -> Plan:
        return plan_for(self.tier)

    @property
    def uploads_per_month(self) -> int:
        return self.plan.uploads_per_month

    @property
    def can_use_vlm(self) -> bool:
        return self.plan.vlm

    @property
    def can_download_pdf(self) -> bool:
        return self.plan.pdf

    @property
    def can_compare(self) -> bool:
        return self.plan.compare

    @property
    def can_embed(self) -> bool:
        return self.plan.embed

    @property
    def can_classroom(self) -> bool:
        return self.plan.classroom

    @property
    def can_api(self) -> bool:
        return self.plan.api


def get_or_create_subscription(user) -> Subscription:
    sub, _ = Subscription.objects.get_or_create(user=user)
    return sub


def uploads_this_month(user) -> int:
    """Uploads charged to `user` this month.

    A student's upload into a classroom is charged to whoever pays for that class: the school's
    owner when the class belongs to an organization, otherwise the teacher. It never counts
    against the student.
    """
    now = timezone.now()
    submission_model = user.submissions.model
    return submission_model.objects.filter(
        models.Q(user=user, classroom__isnull=True)
        | models.Q(classroom__organization__isnull=True, classroom__owner=user)
        | models.Q(classroom__organization__owner=user),
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()
