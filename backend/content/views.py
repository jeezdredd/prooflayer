from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from .models import Submission
from .serializers import SubmissionCreateSerializer, SubmissionDetailSerializer, SubmissionListSerializer
from .validators import validate_file_size, validate_mime_type


class SubmissionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "id"

    def get_queryset(self):
        return Submission.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return SubmissionCreateSerializer
        if self.action == "list":
            return SubmissionListSerializer
        return SubmissionDetailSerializer

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

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        if instance.thumbnail:
            instance.thumbnail.delete(save=False)
        instance.delete()
