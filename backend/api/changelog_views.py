from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttling import PublicReadThrottle

from .models import ChangelogEntry


class ChangelogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ChangelogEntry
        fields = ["slug", "date", "kind", "title_en", "title_ru", "body_en", "body_ru"]


class ChangelogView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicReadThrottle]

    def get(self, request):
        entries = ChangelogEntry.objects.filter(is_published=True)[:200]
        return Response({"entries": ChangelogEntrySerializer(entries, many=True).data})
