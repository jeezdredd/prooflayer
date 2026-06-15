import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    class Tier(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        EDUCATION = "education", "Education"
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
    stripe_customer_id = models.CharField(max_length=64, blank=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=64, blank=True, db_index=True)
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
    def uploads_per_month(self) -> int:
        return {
            self.Tier.FREE: 50,
            self.Tier.PRO: 500,
            self.Tier.EDUCATION: 2000,
            self.Tier.ENTERPRISE: 999999,
        }.get(self.tier, 50)

    @property
    def can_use_vlm(self) -> bool:
        return self.tier in (self.Tier.PRO, self.Tier.EDUCATION, self.Tier.ENTERPRISE)

    @property
    def can_download_pdf(self) -> bool:
        return self.tier in (self.Tier.PRO, self.Tier.EDUCATION, self.Tier.ENTERPRISE)

    @property
    def can_compare(self) -> bool:
        return self.tier in (self.Tier.PRO, self.Tier.EDUCATION, self.Tier.ENTERPRISE)

    @property
    def can_embed(self) -> bool:
        return self.tier in (self.Tier.PRO, self.Tier.EDUCATION, self.Tier.ENTERPRISE)

    @property
    def can_api(self) -> bool:
        return self.tier in (self.Tier.PRO, self.Tier.EDUCATION, self.Tier.ENTERPRISE)


def get_or_create_subscription(user) -> Subscription:
    sub, _ = Subscription.objects.get_or_create(user=user)
    return sub


def uploads_this_month(user) -> int:
    now = timezone.now()
    return user.submissions.filter(
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()
