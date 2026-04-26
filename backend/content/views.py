from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Submission
from .pdf import generate_report_pdf
from .serializers import SubmissionCreateSerializer, SubmissionDetailSerializer, SubmissionListSerializer
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
