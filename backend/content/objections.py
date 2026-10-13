import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from classroom.access import can_supervise, supervised_q, visible_submissions_q
from users.tasks import send_objection_notice

from .models import Submission, VerdictObjection

logger = logging.getLogger(__name__)

REASON_MIN_LENGTH = 10
REASON_MAX_LENGTH = 2000
RESPONSE_MIN_LENGTH = 10
RESPONSE_MAX_LENGTH = 2000


class ObjectionSerializer(serializers.ModelSerializer):
    submission_id = serializers.UUIDField(read_only=True)
    submission_title = serializers.CharField(source="submission.original_filename", read_only=True)
    student = serializers.CharField(source="author.username", read_only=True)
    classroom = serializers.SerializerMethodField()
    overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = VerdictObjection
        fields = (
            "id",
            "submission_id",
            "submission_title",
            "student",
            "classroom",
            "reason",
            "status",
            "decision",
            "response",
            "created_at",
            "due_at",
            "responded_at",
            "overdue",
        )
        read_only_fields = fields

    def get_classroom(self, obj):
        classroom = obj.submission.classroom
        return classroom.name if classroom else None


class ObjectionCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=REASON_MIN_LENGTH, max_length=REASON_MAX_LENGTH, trim_whitespace=True)


class ObjectionRespondSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=VerdictObjection.Decision.choices)
    response = serializers.CharField(min_length=RESPONSE_MIN_LENGTH, max_length=RESPONSE_MAX_LENGTH, trim_whitespace=True)


def can_answer(objection: VerdictObjection, user) -> bool:
    if objection.author_id == user.id:
        return False
    if user.is_staff:
        return True
    classroom = objection.submission.classroom
    return classroom is not None and can_supervise(classroom, user)


def can_see_objection(submission: Submission, user) -> bool:
    if user is None or not user.is_authenticated:
        return False
    if user.is_staff or submission.user_id == user.id:
        return True
    return submission.classroom is not None and can_supervise(submission.classroom, user)


def latest_objection_payload(submission: Submission, user):
    if not can_see_objection(submission, user):
        return None
    objection = (
        VerdictObjection.objects.select_related("submission__classroom", "author")
        .filter(submission=submission)
        .order_by("-created_at")
        .first()
    )
    return ObjectionSerializer(objection).data if objection else None


def _notify(objection: VerdictObjection):
    try:
        send_objection_notice.delay(str(objection.id))
    except Exception:
        logger.exception("objection notice failed objection=%s", objection.id)


class SubmissionObjectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        user = request.user
        queryset = Submission.objects.select_related("classroom")
        if not user.is_staff:
            queryset = queryset.filter(visible_submissions_q(user)).distinct()
        submission = get_object_or_404(queryset, id=id)
        if submission.user_id != user.id:
            raise PermissionDenied("Only the author of the work can object to its verdict.")
        if submission.status != Submission.Status.COMPLETED:
            return Response(
                {"detail": "The analysis is not finished yet."}, status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ObjectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if submission.objections.filter(status=VerdictObjection.Status.OPEN).exists():
            return Response(
                {"detail": "An objection to this verdict is already open."}, status=status.HTTP_409_CONFLICT,
            )
        try:
            with transaction.atomic():
                objection = VerdictObjection.objects.create(
                    submission=submission, author=user, reason=serializer.validated_data["reason"],
                )
        except IntegrityError:
            return Response(
                {"detail": "An objection to this verdict is already open."}, status=status.HTTP_409_CONFLICT,
            )
        transaction.on_commit(lambda: _notify(objection))
        return Response(ObjectionSerializer(objection).data, status=status.HTTP_201_CREATED)


class ObjectionListView(generics.ListAPIView):
    serializer_class = ObjectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = VerdictObjection.objects.select_related("submission__classroom", "author")
        if not user.is_staff:
            queryset = queryset.filter(
                Q(author=user) | supervised_q(user, prefix="submission__classroom__")
            ).distinct()
        wanted = self.request.query_params.get("status")
        if wanted in VerdictObjection.Status.values:
            queryset = queryset.filter(status=wanted)
        return queryset.order_by("-created_at")


class ObjectionRespondView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        serializer = ObjectionRespondSerializer(data=request.data)
        with transaction.atomic():
            objection = get_object_or_404(
                VerdictObjection.objects.select_for_update(of=("self",)).select_related(
                    "submission__classroom", "author",
                ),
                id=id,
            )
            if not can_answer(objection, request.user):
                raise PermissionDenied("Only a supervisor of this class can answer the objection.")
            if objection.status == VerdictObjection.Status.ANSWERED:
                return Response(
                    {"detail": "This objection has already been answered."}, status=status.HTTP_409_CONFLICT,
                )
            serializer.is_valid(raise_exception=True)
            objection.status = VerdictObjection.Status.ANSWERED
            objection.decision = serializer.validated_data["decision"]
            objection.response = serializer.validated_data["response"]
            objection.responded_by = request.user
            objection.responded_at = timezone.now()
            objection.save(update_fields=["status", "decision", "response", "responded_by", "responded_at"])
        return Response(ObjectionSerializer(objection).data)
