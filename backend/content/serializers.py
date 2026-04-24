from rest_framework import serializers

from .models import Submission


class SubmissionCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField()

    class Meta:
        model = Submission
        fields = ("id", "file", "status", "created_at")
        read_only_fields = ("id", "status", "created_at")


class SubmissionListSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()

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
            "thumbnail_url",
            "created_at",
        )

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None


class SubmissionDetailSerializer(serializers.ModelSerializer):
    analysis_results = serializers.SerializerMethodField()
    similar_submissions = serializers.SerializerMethodField()

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
            "phash",
            "dhash",
            "analysis_results",
            "similar_submissions",
            "created_at",
            "updated_at",
        )

    def get_analysis_results(self, obj):
        from analyzers.serializers import AnalysisResultSerializer
        return AnalysisResultSerializer(obj.analysis_results.all(), many=True).data

    def get_similar_submissions(self, obj):
        from .services import find_similar_submissions
        return find_similar_submissions(obj)
