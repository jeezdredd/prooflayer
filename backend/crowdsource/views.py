from django.db.models import Count, Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Vote
from .serializers import VoteCreateSerializer, VoteStatsSerializer


class VoteCreateView(generics.CreateAPIView):
    serializer_class = VoteCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vote, created = Vote.objects.update_or_create(
            user=request.user,
            submission=serializer.validated_data["submission"],
            defaults={"value": serializer.validated_data["value"]},
        )
        output = VoteCreateSerializer(vote)
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(output.data, status=http_status)


class VoteStatsView(APIView):
    def get(self, request, submission_id):
        stats = Vote.objects.filter(submission_id=submission_id).aggregate(
            real_count=Count("id", filter=Q(value=Vote.Value.REAL)),
            fake_count=Count("id", filter=Q(value=Vote.Value.FAKE)),
            uncertain_count=Count("id", filter=Q(value=Vote.Value.UNCERTAIN)),
            total=Count("id"),
        )
        user_vote = Vote.objects.filter(
            user=request.user, submission_id=submission_id
        ).values_list("value", flat=True).first()
        stats["submission_id"] = submission_id
        stats["user_vote"] = user_vote
        serializer = VoteStatsSerializer(stats)
        return Response(serializer.data)
