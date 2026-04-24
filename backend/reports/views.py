from rest_framework import generics, permissions

from .models import Report
from .serializers import ReportCreateSerializer, ReportListSerializer


class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportCreateSerializer

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)


class ReportListView(generics.ListAPIView):
    serializer_class = ReportListSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["status", "reason"]

    def get_queryset(self):
        return Report.objects.select_related("reporter").all()
