from django.core.files.storage import default_storage
from rest_framework import serializers

from .models import AnalyzerConfig, AnalysisResult


class AnalyzerConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyzerConfig
        fields = ("id", "name", "version", "is_active", "weight", "queue")


class AnalysisResultSerializer(serializers.ModelSerializer):
    analyzer_name = serializers.CharField(source="analyzer.name", read_only=True)
    evidence = serializers.SerializerMethodField()

    def get_evidence(self, obj):
        evidence = obj.evidence or {}
        path = evidence.get("heatmap_path")
        if not path:
            return evidence
        try:
            return {**evidence, "heatmap_url": default_storage.url(path)}
        except Exception:
            return evidence

    class Meta:
        model = AnalysisResult
        fields = (
            "id",
            "analyzer_name",
            "confidence",
            "verdict",
            "evidence",
            "execution_time",
            "error_message",
            "created_at",
        )
