from django.core.files.storage import default_storage
from rest_framework import serializers

from .models import AnalyzerConfig, AnalysisResult

WHOLE_IMAGE_AI = {"fake", "likely_fake"}


class AnalyzerConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyzerConfig
        fields = ("id", "name", "version", "is_active", "weight", "queue")


class AnalysisResultSerializer(serializers.ModelSerializer):
    analyzer_name = serializers.CharField(source="analyzer.name", read_only=True)
    evidence = serializers.SerializerMethodField()

    def get_evidence(self, obj):
        evidence = dict(obj.evidence or {})
        for path_key, url_key in (("heatmap_path", "heatmap_url"), ("map_path", "map_url")):
            path = evidence.get(path_key)
            if not path:
                continue
            try:
                evidence[url_key] = default_storage.url(path)
            except Exception:
                continue
        if obj.analyzer.name == "manipulation_map" and obj.submission.final_verdict in WHOLE_IMAGE_AI:
            evidence.pop("map_url", None)
            evidence["regions"] = []
            evidence["status"] = "abstain"
            evidence["reason"] = "whole_image_ai"
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
