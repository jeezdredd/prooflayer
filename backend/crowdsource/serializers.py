from rest_framework import serializers

from .models import Vote


class VoteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ("id", "submission", "value", "created_at")
        read_only_fields = ("id", "created_at")


class VoteStatsSerializer(serializers.Serializer):
    submission_id = serializers.UUIDField()
    real_count = serializers.IntegerField()
    fake_count = serializers.IntegerField()
    uncertain_count = serializers.IntegerField()
    total = serializers.IntegerField()
    user_vote = serializers.CharField(allow_null=True)
