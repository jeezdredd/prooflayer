from rest_framework import serializers

from .models import Submission


class SubmissionCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField()

    class Meta:
        model = Submission
        fields = ("id", "file", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")


class SubmissionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = (
            "id",
            "original_filename",
            "mime_type",
            "file_size",
            "status",
            "final_score",
            "final_verdict",
            "is_known_fake",
            "created_at",
        )


class SubmissionDetailSerializer(serializers.ModelSerializer):
    analysis_results = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = (
            "id",
            "original_filename",
            "mime_type",
            "file_size",
            "sha256_hash",
            "status",
            "metadata",
            "final_score",
            "final_verdict",
            "is_known_fake",
            "analysis_results",
            "created_at",
            "updated_at",
        )

    def get_analysis_results(self, obj):
        from analyzers.serializers import AnalysisResultSerializer
        return AnalysisResultSerializer(obj.analysis_results.all(), many=True).data
