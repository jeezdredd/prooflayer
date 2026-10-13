from rest_framework import serializers

from .models import ProvenanceResult


class ProvenanceResultSerializer(serializers.ModelSerializer):
    is_sensitive = serializers.SerializerMethodField()

    class Meta:
        model = ProvenanceResult
        fields = (
            "id", "source_type", "source_url", "title", "similarity_score", "raw_data", "found_at", "is_sensitive",
        )

    def get_is_sensitive(self, obj):
        matched = obj.raw_data.get("submission_id") if isinstance(obj.raw_data, dict) else None
        return bool(matched) and matched in self.context.get("sensitive_submission_ids", set())
