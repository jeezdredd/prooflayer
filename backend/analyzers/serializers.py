from rest_framework import serializers

from .models import AnalyzerConfig, AnalysisResult


class AnalyzerConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyzerConfig
        fields = ("id", "name", "version", "is_active", "weight", "queue")


class AnalysisResultSerializer(serializers.ModelSerializer):
    analyzer_name = serializers.CharField(source="analyzer.name", read_only=True)

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
