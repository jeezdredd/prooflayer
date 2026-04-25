from rest_framework import serializers

from .models import ProvenanceResult


class ProvenanceResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProvenanceResult
        fields = ("id", "source_type", "source_url", "title", "similarity_score", "raw_data", "found_at")
