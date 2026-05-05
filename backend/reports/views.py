from django.db import IntegrityError
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Report
from .serializers import ReportCreateSerializer, ReportListSerializer


class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(reporter=request.user)
        except IntegrityError:
            return Response(
                {"detail": "You have already reported this submission."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReportListView(generics.ListAPIView):
    serializer_class = ReportListSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["status", "reason"]

    def get_queryset(self):
        return Report.objects.select_related("reporter").all()
