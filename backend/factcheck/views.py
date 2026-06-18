from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsVerifiedUser

from .tasks import run_factcheck


class FactCheckView(APIView):
    permission_classes = [IsVerifiedUser]

    def post(self, request):
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"error": "text is required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(text) > 10000:
            return Response({"error": "text too long (max 10000 chars)"}, status=status.HTTP_400_BAD_REQUEST)
        task = run_factcheck.delay(text)
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)


class FactCheckStatusView(APIView):
    permission_classes = [IsVerifiedUser]

    def get(self, request, task_id):
        payload = cache.get(f"fc:{task_id}")
        if payload is None:
            return Response({"stage": "pending", "progress": 0})
        return Response(payload)
