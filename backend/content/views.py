from django.http import HttpResponse
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Submission, VerdictOverride
from .pdf import generate_report_pdf
from .serializers import (
    ReviewQueueSerializer,
    SubmissionCreateSerializer,
    SubmissionDetailSerializer,
    SubmissionListSerializer,
    VerdictOverrideSerializer,
)
from .throttles import UploadRateThrottle
from .validators import validate_file_size, validate_mime_type


class SubmissionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "id"
    filterset_fields = {
        "status": ["exact"],
        "final_verdict": ["exact"],
        "is_known_fake": ["exact"],
        "created_at": ["gte", "lte"],
    }
    search_fields = ["original_filename"]
    ordering_fields = ["created_at", "final_score", "file_size"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Submission.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return SubmissionCreateSerializer
        if self.action == "list":
            return SubmissionListSerializer
        return SubmissionDetailSerializer

    def get_throttles(self):
        if self.action == "create":
            return [UploadRateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response({"file": ["No file provided."]}, status=status.HTTP_400_BAD_REQUEST)

        validate_file_size(file)
        mime_type = validate_mime_type(file)

        submission = Submission.objects.create(
            user=request.user,
            file=file,
            original_filename=file.name,
            mime_type=mime_type,
            file_size=file.size,
        )

        from content.tasks import process_submission
        process_submission.delay(str(submission.id))

        serializer = SubmissionCreateSerializer(submission)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="compare")
    def compare(self, request):
        ids = (request.query_params.get("ids") or "").split(",")
        ids = [i.strip() for i in ids if i.strip()][:2]
        if len(ids) != 2:
            return Response({"detail": "Provide exactly 2 submission ids: ?ids=a,b"}, status=status.HTTP_400_BAD_REQUEST)
        submissions = list(self.get_queryset().filter(id__in=ids))
        if len(submissions) != 2:
            return Response({"detail": "One or both submissions not found."}, status=status.HTTP_404_NOT_FOUND)
        ordered = [s for sid in ids for s in submissions if str(s.id) == sid]
        serializer = SubmissionDetailSerializer(ordered, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="report.pdf")
    def report_pdf(self, request, id=None):
        submission = self.get_object()
        if submission.status != "completed":
            return Response({"detail": "Report available only for completed submissions."}, status=status.HTTP_400_BAD_REQUEST)
        pdf_buffer = generate_report_pdf(submission, request)
        filename = f"prooflayer_report_{submission.id}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        if instance.thumbnail:
            instance.thumbnail.delete(save=False)
        instance.delete()


REVIEW_VERDICTS = ("needs_review", "inconclusive")
ALLOWED_OVERRIDE_VERDICTS = {"authentic", "suspicious", "likely_fake", "fake", "inconclusive"}


class ReviewQueueView(generics.ListAPIView):
    serializer_class = ReviewQueueSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return (
            Submission.objects.filter(
                status=Submission.Status.COMPLETED,
                final_verdict__in=REVIEW_VERDICTS,
            )
            .select_related("user")
            .order_by("-created_at")
        )


class VerdictOverrideView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, id):
        try:
            submission = Submission.objects.get(id=id)
        except Submission.DoesNotExist:
            return Response({"detail": "Submission not found."}, status=status.HTTP_404_NOT_FOUND)

        new_verdict = (request.data.get("verdict") or "").strip().lower()
        reason = (request.data.get("reason") or "").strip()
        if new_verdict not in ALLOWED_OVERRIDE_VERDICTS:
            return Response(
                {"verdict": [f"Must be one of {sorted(ALLOWED_OVERRIDE_VERDICTS)}."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous = submission.final_verdict
        VerdictOverride.objects.create(
            submission=submission,
            reviewer=request.user,
            previous_verdict=previous,
            new_verdict=new_verdict,
            reason=reason,
        )
        submission.final_verdict = new_verdict
        submission.save(update_fields=["final_verdict", "updated_at"])

        return Response(
            VerdictOverrideSerializer(submission.verdict_overrides.first()).data,
            status=status.HTTP_201_CREATED,
        )


class WidgetEmbedView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request, sha256):
        submission = (
            Submission.objects.filter(sha256_hash=sha256, status=Submission.Status.COMPLETED)
            .order_by("-created_at")
            .first()
        )
        if not submission:
            return Response(
                {
                    "found": False,
                    "verdict": "unknown",
                    "score": None,
                    "is_known_fake": False,
                },
                headers={"Access-Control-Allow-Origin": "*"},
            )

        return Response(
            {
                "found": True,
                "submission_id": str(submission.id),
                "verdict": submission.final_verdict or "inconclusive",
                "score": submission.final_score,
                "is_known_fake": submission.is_known_fake,
                "submitted_at": submission.created_at.isoformat(),
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )
