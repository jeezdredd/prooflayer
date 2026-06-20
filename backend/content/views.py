import datetime
import io
from urllib.parse import urlparse

import requests as http_requests

from common.url_safety import UnsafeUrlError, safe_get, validate_public_url
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db.models import Count, Avg
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated

from users.permissions import IsVerifiedUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Submission, VerdictOverride, AnonymousQuota
from .pdf import generate_report_pdf
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
from billing.models import get_or_create_subscription, uploads_this_month
from content.tasks import process_submission

User = get_user_model()


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

    def get_permissions(self):
        if self.action == "create":
            return [IsVerifiedUser()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            sub = get_or_create_subscription(request.user)
            used = uploads_this_month(request.user)
            if used >= sub.uploads_per_month:
                return Response(
                    {
                        "detail": f"Monthly upload limit reached ({sub.uploads_per_month} uploads). Upgrade to Pro for more.",
                        "code": "upload_limit_reached",
                        "limit": sub.uploads_per_month,
                        "used": used,
                        "tier": sub.tier,
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

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

        process_submission.delay(str(submission.id))

        serializer = SubmissionCreateSerializer(submission)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="toggle-public")
    def toggle_public(self, request, id=None):
        submission = self.get_object()
        if submission.status != "completed":
            return Response({"detail": "Only completed submissions can be made public."}, status=status.HTTP_400_BAD_REQUEST)
        submission.is_public = not submission.is_public
        submission.save(update_fields=["is_public"])
        return Response({"is_public": submission.is_public})

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

    def perform_destroy(self, instance):
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
        new_label = label_map.get(new_verdict)
        if new_label:
            submission.verified_label = new_label
            submission.approved_for_training = True
            updated_fields += ["verified_label", "approved_for_training"]
        submission.save(update_fields=updated_fields)

        return Response(
            VerdictOverrideSerializer(submission.verdict_overrides.first()).data,
            status=status.HTTP_201_CREATED,
        )


class PublicFeedView(generics.ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_serializer_class(self):
        return PublicSubmissionSerializer

    def get_queryset(self):
        return (
            Submission.objects.filter(is_public=True, status=Submission.Status.COMPLETED)
            .select_related("user")
            .order_by("-created_at")[:100]
        )


class PublicSubmissionDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = "id"

    def get_serializer_class(self):
        return PublicSubmissionSerializer

    def get_queryset(self):
        return Submission.objects.filter(is_public=True, status=Submission.Status.COMPLETED).select_related("user")


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


class AnalyzeUrlView(APIView):
    permission_classes = [AllowAny]
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
            owner = User.objects.filter(is_staff=True).first()
            if owner is None:
                return Response(
                    {"detail": "Service not configured."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

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
    authentication_classes = []

    def get(self, request, id):
        try:
            sub = Submission.objects.get(id=id)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": str(sub.id),
            "status": sub.status,
            "final_verdict": sub.final_verdict,
            "final_score": sub.final_score,
        })
