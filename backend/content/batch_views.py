import csv
import io

from django.http import HttpResponse
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from classroom.access import classroom_for_upload, quota_owner
from users.models import ApiKey
from users.permissions import IsVerifiedUser

from .intake import QuotaExceeded, check_quota, collect_uploads, create_submission
from .models import Batch
from .throttles import BatchRateThrottle

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
CSV_COLUMNS = (
    "submission_id", "original_filename", "status", "final_verdict", "final_score",
    "tribunal_version", "mime_type", "sha256", "created_at",
)


def csv_safe(value) -> str:
    """Neutralise spreadsheet formula injection: filenames are user-controlled."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


class BatchItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    original_filename = serializers.CharField()
    mime_type = serializers.CharField()
    status = serializers.CharField()
    final_verdict = serializers.CharField()
    final_score = serializers.FloatField(allow_null=True)
    tribunal_version = serializers.CharField()


class BatchSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = ("id", "name", "created_at", "skipped", "summary", "items")

    def _subs(self, obj):
        cache = getattr(obj, "_prefetched_subs", None)
        if cache is None:
            cache = list(obj.submissions.order_by("original_filename"))
            obj._prefetched_subs = cache
        return cache

    def get_items(self, obj):
        return BatchItemSerializer(self._subs(obj), many=True).data

    def get_summary(self, obj):
        subs = self._subs(obj)
        by_status, by_verdict = {}, {}
        for s in subs:
            by_status[s.status] = by_status.get(s.status, 0) + 1
            if s.final_verdict:
                by_verdict[s.final_verdict] = by_verdict.get(s.final_verdict, 0) + 1
        done = by_status.get("completed", 0) + by_status.get("failed", 0)
        return {"total": len(subs), "done": done, "by_status": by_status, "by_verdict": by_verdict}


class BatchListSerializer(serializers.ModelSerializer):
    total = serializers.IntegerField(source="submissions.count", read_only=True)

    class Meta:
        model = Batch
        fields = ("id", "name", "created_at", "total")


class BatchViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    lookup_field = "id"
    permission_classes = [IsVerifiedUser]

    def get_queryset(self):
        return Batch.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return BatchListSerializer if self.action == "list" else BatchSerializer

    def get_throttles(self):
        if self.action == "create":
            return [BatchRateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        files = request.FILES.getlist("files") or request.FILES.getlist("file")
        if not files:
            return Response({"files": ["No files provided."]}, status=status.HTTP_400_BAD_REQUEST)
        intake = collect_uploads(files)
        if not intake.accepted:
            return Response(
                {"files": ["None of the files are a supported type."], "skipped": intake.skipped},
                status=status.HTTP_400_BAD_REQUEST,
            )
        classroom = classroom_for_upload(request.user, request.data.get("classroom"))
        try:
            check_quota(quota_owner(request.user, classroom), requested=len(intake.accepted))
        except QuotaExceeded as exc:
            return Response(exc.as_response_data(), status=status.HTTP_402_PAYMENT_REQUIRED)

        batch = Batch.objects.create(
            user=request.user,
            name=(request.data.get("name") or "")[:120],
            classroom=classroom,
            skipped=intake.skipped,
        )
        api_key = request.auth if isinstance(request.auth, ApiKey) else None
        for upload, mime_type in intake.accepted:
            create_submission(request.user, upload, mime_type, batch=batch, api_key=api_key, classroom=classroom)
        return Response(BatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="export.csv")
    def export_csv(self, request, id=None):
        batch = self.get_object()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(CSV_COLUMNS)
        for s in batch.submissions.order_by("original_filename"):
            writer.writerow([
                csv_safe(s.id), csv_safe(s.original_filename), csv_safe(s.status), csv_safe(s.final_verdict),
                "" if s.final_score is None else f"{s.final_score:.4f}", csv_safe(s.tribunal_version),
                csv_safe(s.mime_type), csv_safe(s.sha256_hash), s.created_at.isoformat(),
            ])
        response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="prooflayer_batch_{batch.id}.csv"'
        return response
