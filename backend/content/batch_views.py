import csv
import io
import json

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from classroom.access import (
    can_supervise,
    classroom_for_upload,
    deny_student_only,
    quota_owner,
    supervised_q,
    upload_author,
)
from classroom.attention import attention_q
from classroom.export import class_table, csv_safe, pick_lang
from classroom.serializers import ClassSubmissionSerializer, class_context, is_unattributed
from users.models import ApiKey
from users.permissions import IsVerifiedUser

from .intake import QuotaExceeded, check_quota, collect_uploads, create_submission
from .models import Batch
from .throttles import BatchRateThrottle

__all__ = ["BatchViewSet", "csv_safe"]

CSV_COLUMNS = (
    "submission_id", "original_filename", "status", "final_verdict", "final_score",
    "tribunal_version", "mime_type", "sha256", "created_at",
)


def file_students(raw) -> dict[str, str] | None:
    if raw in (None, ""):
        return {}
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return None
    if not isinstance(value, dict):
        return None
    return {str(name): "" if student is None else str(student) for name, student in value.items()}


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
    classroom = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = ("id", "name", "created_at", "skipped", "summary", "items", "classroom")

    def _subs(self, obj):
        cache = getattr(obj, "_prefetched_subs", None)
        if cache is None:
            queryset = obj.submissions.order_by("original_filename")
            if obj.classroom_id:
                queryset = queryset.select_related("user", "uploaded_by", "plagiarism_report").prefetch_related(
                    "analysis_results__analyzer", "objections",
                )
            cache = list(queryset)
            obj._prefetched_subs = cache
        return cache

    def get_items(self, obj):
        if obj.classroom_id:
            request = self.context.get("request")
            viewer = request.user if request is not None else None
            return ClassSubmissionSerializer(self._subs(obj), many=True, context=class_context(obj.classroom, viewer)).data
        return BatchItemSerializer(self._subs(obj), many=True).data

    def get_classroom(self, obj):
        if not obj.classroom_id:
            return None
        classroom = obj.classroom
        request = self.context.get("request")
        supervising = bool(request) and can_supervise(classroom, request.user)
        return {
            "id": str(classroom.id),
            "name": classroom.name,
            "organization_slug": classroom.organization.slug if classroom.organization_id else None,
            "role": "teacher" if supervising else "student",
        }

    def get_summary(self, obj):
        subs = self._subs(obj)
        by_status, by_verdict = {}, {}
        for s in subs:
            by_status[s.status] = by_status.get(s.status, 0) + 1
            if s.final_verdict:
                by_verdict[s.final_verdict] = by_verdict.get(s.final_verdict, 0) + 1
        done = by_status.get("completed", 0) + by_status.get("failed", 0)
        summary = {"total": len(subs), "done": done, "by_status": by_status, "by_verdict": by_verdict}
        if obj.classroom_id:
            summary["flagged"] = obj.submissions.filter(attention_q()).count()
        return summary


class BatchListSerializer(serializers.ModelSerializer):
    total = serializers.IntegerField(source="submissions.count", read_only=True)

    class Meta:
        model = Batch
        fields = ("id", "name", "created_at", "total")


class BatchViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    lookup_field = "id"
    permission_classes = [IsVerifiedUser]

    def get_queryset(self):
        user = self.request.user
        if self.action == "list":
            return Batch.objects.filter(user=user)
        return (
            Batch.objects.filter(Q(user=user) | supervised_q(user, prefix="classroom__"))
            .select_related("classroom__organization")
            .distinct()
        )

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
        assigned = file_students(request.data.get("students"))
        if assigned is None:
            return Response({"students": ["Expected file names mapped to student ids."]}, status=status.HTTP_400_BAD_REQUEST)
        classroom = classroom_for_upload(request.user, request.data.get("classroom"))
        if classroom is None:
            deny_student_only(request.user)
        author, uploaded_by = upload_author(request.user, classroom, request.data.get("student"))
        authors = {student: upload_author(request.user, classroom, student) for student in set(assigned.values())}
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
            student = assigned.get(upload.name)
            owner, by = authors[student] if student is not None else (author, uploaded_by)
            create_submission(owner, upload, mime_type, batch=batch, api_key=api_key, classroom=classroom, uploaded_by=by)
        return Response(BatchSerializer(batch, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="export.csv")
    def export_csv(self, request, id=None):
        batch = self.get_object()
        if batch.classroom_id and can_supervise(batch.classroom, request.user):
            context = class_context(batch.classroom)
            rows = BatchSerializer(context={"request": request})._subs(batch)
            body = class_table(rows, pick_lang(request), lambda s: is_unattributed(s, context))
            response = HttpResponse(body, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="prooflayer_batch_{batch.id}.csv"'
            return response
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
