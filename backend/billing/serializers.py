from rest_framework import serializers

from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = (
            "tier",
            "status",
            "current_period_end",
            "can_use_vlm",
            "can_download_pdf",
            "can_compare",
            "can_embed",
            "can_api",
            "uploads_per_month",
        )
        read_only_fields = fields
