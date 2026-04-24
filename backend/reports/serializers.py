from rest_framework import serializers

from .models import Report


class ReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("id", "submission", "reason", "description", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")


class ReportListSerializer(serializers.ModelSerializer):
    reporter_email = serializers.EmailField(source="reporter.email", read_only=True)

    class Meta:
        model = Report
        fields = (
            "id",
            "reporter_email",
            "submission",
            "reason",
            "description",
            "status",
            "admin_notes",
            "created_at",
            "updated_at",
        )
