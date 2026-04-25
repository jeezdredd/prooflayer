from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import analyze_text


class FactCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"error": "text is required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(text) > 10000:
            return Response({"error": "text too long (max 10000 chars)"}, status=status.HTTP_400_BAD_REQUEST)
        result = analyze_text(text)
        return Response(result)
