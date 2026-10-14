from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ("user", "tier_badge", "status_badge", "current_period_end", "cancel_scheduled", "updated_at")
    list_filter = ("tier", "status", "cancel_scheduled")
    search_fields = ("user__email", "paddle_customer_id", "paddle_subscription_id")
    list_select_related = ("user",)
    raw_id_fields = ("user",)
    readonly_fields = ("paddle_customer_id", "paddle_subscription_id", "created_at", "updated_at")
    ordering = ("-updated_at",)

    @display(
        description="Tier",
        ordering="tier",
        label={"free": "", "pro": "primary", "education": "info", "university": "info", "enterprise": "success"},
    )
    def tier_badge(self, obj: Subscription) -> str:
        return obj.tier

    @display(
        description="Status",
        ordering="status",
        label={"active": "success", "trialing": "info", "past_due": "danger", "cancelled": "warning"},
    )
    def status_badge(self, obj: Subscription) -> str:
        return obj.status
