from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AnalyzerConfig, AnalysisResult, RetrainRun
from .serializers import AnalyzerConfigSerializer, AnalysisResultSerializer
from .tasks import run_weekly_retrain

ALLOWED_MEDIA = {"image", "video", "audio"}


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


class RetrainTriggerView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        media_type = (request.data.get("media_type") or "image").strip().lower()
        if media_type not in ALLOWED_MEDIA:
            return Response(
                {"error": f"media_type must be one of {sorted(ALLOWED_MEDIA)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        task = run_weekly_retrain.delay(media_type)
        return Response(
            {"task_id": task.id, "media_type": media_type},
            status=status.HTTP_202_ACCEPTED,
        )


class RetrainStatusView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        runs = RetrainRun.objects.order_by("-started_at")[:10]
        return Response([
            {
                "id": str(r.id),
                "media_type": r.media_type,
                "status": r.status,
                "samples_used": r.samples_used,
                "hf_revision": r.hf_revision,
                "error": r.error,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ])
