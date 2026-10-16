import datetime
import io
from urllib.parse import urlparse

import requests as http_requests
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analyzers.training import snapshot
from billing.models import get_or_create_subscription, uploads_this_month
from billing.permissions import CanCompare
from classroom.access import (
    NotStudentAccount,
    classroom_for_upload,
    deny_student_only,
    quota_owner,
    supervised_q,
    upload_author,
    visible_submissions_q,
)
from common.age import can_view_sensitive
from common.url_safety import UnsafeUrlError, safe_get, validate_public_url
from content.tasks import process_submission
from users.models import ApiKey
from users.permissions import IsVerifiedUser

from .intake import QuotaExceeded, check_quota, create_submission
from .models import AnonymousQuota, Submission, VerdictOverride
from .pdf import generate_report_pdf
from .reanalysis import restart_analysis
from .sensitivity import (
    ADULT_REQUIRED_CODE,
    ADULT_REQUIRED_DETAIL,
    OptionalViewerAuthentication,
    for_viewer,
    parse_flag,
)
from .serializers import (
    PublicSubmissionSerializer,
    ReviewQueueSerializer,
    SubmissionCreateSerializer,
    SubmissionDetailSerializer,
    SubmissionListSerializer,
    VerdictOverrideSerializer,
)
from .throttles import UploadRateThrottle
from .validators import validate_file_size, validate_mime_type

User = get_user_model()

ANONYMOUS_OWNER_EMAIL = "anonymous@prooflayer.invalid"


def get_anonymous_owner():
    """Service account that owns anonymous analyze-url submissions.

    Created inactive and unusable-password so it can never be logged into, and kept
    separate from real staff accounts so anonymous traffic does not land in an admin's
    submission list or count against their quota.
    """
    owner, created = User.objects.get_or_create(
        email=ANONYMOUS_OWNER_EMAIL,
        defaults={"is_active": False, "is_verified": True},
    )
    if created:
        owner.set_unusable_password()
        owner.save(update_fields=["password"])
    return owner


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
        user = self.request.user
        if self.action == "list":
            return Submission.objects.filter(user=user)
        if can_view_sensitive(user):
            return Submission.objects.filter(visible_submissions_q(user)).distinct()
        supervised = supervised_q(user, prefix="classroom__") & Q(is_sensitive=False)
        return Submission.objects.filter(Q(user=user) | supervised).distinct()

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

    def get_permissions(self):
        if self.action == "create":
            return [IsVerifiedUser()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response({"file": ["No file provided."]}, status=status.HTTP_400_BAD_REQUEST)
        classroom = classroom_for_upload(request.user, request.data.get("classroom"))
        if classroom is None:
            deny_student_only(request.user)
        author, uploaded_by = upload_author(request.user, classroom, request.data.get("student"))
        try:
            check_quota(quota_owner(request.user, classroom))
        except QuotaExceeded as exc:
            return Response(exc.as_response_data(), status=status.HTTP_402_PAYMENT_REQUIRED)

        validate_file_size(file)
        mime_type = validate_mime_type(file)
        submission = create_submission(
            author, file, mime_type,
            api_key=request.auth if isinstance(request.auth, ApiKey) else None,
            classroom=classroom,
            uploaded_by=uploaded_by,
        )
        serializer = SubmissionCreateSerializer(submission)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="toggle-public")
    def toggle_public(self, request, id=None):
        deny_student_only(request.user)
        submission = self.get_object()
        if submission.user_id != request.user.id:
            return Response({"detail": "Only the author can change visibility."}, status=status.HTTP_403_FORBIDDEN)
        if submission.status != "completed":
            return Response({"detail": "Only completed submissions can be made public."}, status=status.HTTP_400_BAD_REQUEST)
        if submission.is_public:
            submission.is_public = False
            submission.save(update_fields=["is_public"])
            return Response({"is_public": False, "is_sensitive": submission.is_sensitive})
        if submission.classroom_id:
            return Response({"detail": "Work handed in to a class cannot be made public."}, status=status.HTTP_403_FORBIDDEN)
        if not can_view_sensitive(request.user):
            return Response(
                {"detail": ADULT_REQUIRED_DETAIL, "code": ADULT_REQUIRED_CODE},
                status=status.HTTP_403_FORBIDDEN,
            )
        submission.is_public = True
        updated_fields = ["is_public"]
        if parse_flag(request.data.get("sensitive")):
            submission.is_sensitive = True
            updated_fields.append("is_sensitive")
        submission.save(update_fields=updated_fields)
        return Response({"is_public": True, "is_sensitive": submission.is_sensitive})

    @action(detail=False, methods=["get"], url_path="compare", permission_classes=[CanCompare])
    def compare(self, request):
        deny_student_only(request.user)
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
        sub = get_or_create_subscription(request.user)
        if not sub.can_download_pdf:
            return Response({"detail": "PDF reports require Pro subscription.", "code": "upgrade_required"}, status=status.HTTP_402_PAYMENT_REQUIRED)
        submission = self.get_object()
        if submission.status != "completed":
            return Response({"detail": "Report available only for completed submissions."}, status=status.HTTP_400_BAD_REQUEST)
        pdf_buffer = generate_report_pdf(submission, request)
        filename = f"prooflayer_report_{submission.id}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["post"], url_path="reanalyze")
    def reanalyze(self, request, id=None):
        deny_student_only(request.user)
        submission = self.get_object()
        if submission.status not in (Submission.Status.COMPLETED, Submission.Status.FAILED):
            return Response({"detail": "Submission is still being analyzed."}, status=status.HTTP_409_CONFLICT)
        if not submission.file:
            return Response(
                {"detail": "The file was deleted under the retention policy; upload it again to re-check."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            check_quota(quota_owner(request.user, submission.classroom))
        except QuotaExceeded as exc:
            return Response(exc.as_response_data(), status=status.HTTP_402_PAYMENT_REQUIRED)
        restart_analysis(submission)
        return Response({"id": str(submission.id), "status": submission.status}, status=status.HTTP_202_ACCEPTED)

    def perform_destroy(self, instance):
        if instance.user_id != self.request.user.id:
            raise PermissionDenied("Only the author can delete a submission.")
        if instance.file:
            instance.file.delete(save=False)
        if instance.thumbnail:
            instance.thumbnail.delete(save=False)
        instance.delete()

    @action(detail=False, methods=["get"], url_path="stats", permission_classes=[IsAuthenticated])
    def stats(self, request):
        qs = Submission.objects.filter(user=request.user)
        total = qs.count()
        by_verdict = dict(
            qs.exclude(final_verdict="")
            .values_list("final_verdict")
            .annotate(c=Count("id"))
        )
        by_status = dict(qs.values_list("status").annotate(c=Count("id")))
        avg_score = qs.filter(status="completed", final_score__isnull=False).aggregate(a=Avg("final_score"))["a"]
        known_fake_hits = qs.filter(is_known_fake=True).count()
        return Response({
            "total": total,
            "by_verdict": by_verdict,
            "by_status": by_status,
            "avg_score": round(avg_score, 4) if avg_score is not None else None,
            "known_fake_hits": known_fake_hits,
        })


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
        sensitive = None
        if "is_sensitive" in request.data:
            sensitive = parse_flag(request.data.get("is_sensitive"))
            if sensitive is None:
                return Response({"is_sensitive": ["Must be a boolean."]}, status=status.HTTP_400_BAD_REQUEST)

        previous = submission.final_verdict
        VerdictOverride.objects.create(
            submission=submission,
            reviewer=request.user,
            previous_verdict=previous,
            new_verdict=new_verdict,
            reason=reason,
        )
        submission.final_verdict = new_verdict
        label_map = {
            "authentic": "real",
            "fake": "fake",
            "likely_fake": "fake",
        }
        updated_fields = ["final_verdict", "updated_at"]
        if sensitive is not None:
            submission.is_sensitive = sensitive
            updated_fields.append("is_sensitive")
        new_label = label_map.get(new_verdict)
        if new_label:
            submission.verified_label = new_label
            updated_fields.append("verified_label")
            if submission.classroom_id is None:
                submission.approved_for_training = True
                updated_fields.append("approved_for_training")
        submission.save(update_fields=updated_fields)
        if submission.approved_for_training:
            snapshot(submission)

        return Response(
            VerdictOverrideSerializer(submission.verdict_overrides.first()).data,
            status=status.HTTP_201_CREATED,
        )


class PublicFeedView(generics.ListAPIView):
    permission_classes = [AllowAny, NotStudentAccount]
    authentication_classes = [OptionalViewerAuthentication]

    def get_serializer_class(self):
        return PublicSubmissionSerializer

    def get_queryset(self):
        public = Submission.objects.filter(is_public=True, status=Submission.Status.COMPLETED)
        return (
            for_viewer(public, self.request.user)
            .select_related("user")
            .order_by("-created_at")[:100]
        )


class PublicSubmissionDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny, NotStudentAccount]
    authentication_classes = [OptionalViewerAuthentication]
    lookup_field = "id"

    def get_serializer_class(self):
        return PublicSubmissionSerializer

    def get_queryset(self):
        public = Submission.objects.filter(is_public=True, status=Submission.Status.COMPLETED)
        return for_viewer(public, self.request.user).select_related("user")


class AnalyzeUrlView(APIView):
    permission_classes = [AllowAny, NotStudentAccount]
    MAX_SIZE = 20 * 1024 * 1024

    def post(self, request):
        url = (request.data.get("url") or "").strip()
        try:
            validate_public_url(url)
        except UnsafeUrlError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.is_authenticated:
            if not (request.user.is_staff or request.user.is_superuser):
                sub = get_or_create_subscription(request.user)
                used = uploads_this_month(request.user)
                if used >= sub.uploads_per_month:
                    return Response(
                        {"code": "upload_limit_reached"},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
            owner = request.user
        else:
            allowed, remaining = AnonymousQuota.check_and_increment(request, limit=5)
            if not allowed:
                now = timezone.now()
                tomorrow = (now + datetime.timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                resets_in = int((tomorrow - now).total_seconds())
                return Response(
                    {"code": "anonymous_limit_reached", "resets_in": resets_in},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            owner = get_anonymous_owner()

        try:
            resp = safe_get(url, timeout=10)
            resp.raise_for_status()
            data = b""
            for chunk in resp.iter_content(chunk_size=65536):
                data += chunk
                if len(data) > self.MAX_SIZE:
                    return Response(
                        {"detail": "File too large (max 20 MB)."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        except UnsafeUrlError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except http_requests.RequestException:
            return Response(
                {"detail": "Could not fetch URL"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filename = urlparse(url).path.split("/")[-1] or "image"

        buf = io.BytesIO(data)
        buf.name = filename
        try:
            mime_type = validate_mime_type(buf)
        except Exception:
            return Response(
                {"detail": "Unsupported file type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file_obj = ContentFile(data, name=filename)
        submission = Submission.objects.create(
            user=owner,
            file=file_obj,
            original_filename=filename,
            mime_type=mime_type,
            file_size=len(data),
            source_url=url,
        )

        process_submission.delay(str(submission.id))

        return Response({"submission_id": str(submission.id)}, status=status.HTTP_201_CREATED)


class SubmissionStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, id):
        try:
            sub = Submission.objects.get(id=id)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        user = request.user
        owns = user.is_authenticated and (sub.user_id == user.id or user.is_staff)
        public_for_viewer = sub.is_public and (not sub.is_sensitive or can_view_sensitive(user))
        if not (public_for_viewer or owns or sub.source_url):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": str(sub.id),
            "status": sub.status,
            "final_verdict": sub.final_verdict,
            "final_score": sub.final_score,
        })
