from rest_framework import generics

from .models import AnalyzerConfig, AnalysisResult
from .serializers import AnalyzerConfigSerializer, AnalysisResultSerializer


class AnalyzerConfigListView(generics.ListAPIView):
    serializer_class = AnalyzerConfigSerializer
    queryset = AnalyzerConfig.objects.filter(is_active=True)


class AnalysisResultListView(generics.ListAPIView):
    serializer_class = AnalysisResultSerializer

    def get_queryset(self):
        submission_id = self.kwargs["submission_id"]
        return AnalysisResult.objects.filter(
            submission_id=submission_id,
            submission__user=self.request.user,
        ).select_related("analyzer")
