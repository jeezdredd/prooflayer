import csv
import io
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.permissions import tier_feature
from content.batch_views import csv_safe
from content.models import Submission
from users.permissions import IsVerifiedUser

from .access import can_supervise, supervised_q
from .models import Classroom, Membership, ShadowSet
from .radar import class_radar
from .shadow import DAILY_SETS, prompt_language, sets_today
from .tasks import build_shadow_set
from .serializers import ClassroomSerializer, ClassSubmissionSerializer, MemberSerializer, ShadowSetSerializer

FLAGGED_VERDICTS = ("fake", "likely_fake", "suspicious", "needs_review")
TIMELINE_DAYS = 30
RADAR_DAYS = 60
RADAR_MAX_DAYS = 365
CanCreateClassroom = tier_feature("can_classroom", "Classroom")


def _originality(submission) -> str:
    report = getattr(submission, "plagiarism_report", None)
    if report is None or report.originality is None:
        return ""
    return f"{report.originality:.1f}"


class ClassroomViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ClassroomSerializer
    lookup_field = "id"
    pagination_class = None

    def get_permissions(self):
        if self.action == "create":
            return [IsVerifiedUser(), CanCreateClassroom()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        return (
            Classroom.objects.filter(supervised_q(user) | Q(memberships__user=user))
            .annotate(student_count=Count("memberships", distinct=True))
            .select_related("owner", "organization")
            .distinct()
        )

    def _owned(self):
        classroom = self.get_object()
        if not can_supervise(classroom, self.request.user):
            raise PermissionDenied("Only the teacher can do this.")
        return classroom

    def perform_create(self, serializer):
        classroom = Classroom.create_for(
            self.request.user, serializer.validated_data["name"], level=serializer.validated_data.get("level"),
        )
        serializer.instance = Classroom.objects.annotate(student_count=Count("memberships")).get(pk=classroom.pk)

    def perform_update(self, serializer):
        if not can_supervise(serializer.instance, self.request.user):
            raise PermissionDenied("Only the teacher can edit the classroom.")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="rotate-code")
    def rotate_code(self, request, id=None):
        classroom = self._owned()
        return Response({"join_code": classroom.rotate_code()})

    @action(detail=True, methods=["get"])
    def roster(self, request, id=None):
        classroom = self._owned()
        members = (
            Membership.objects.filter(classroom=classroom)
            .select_related("user")
            .annotate(
                total=Count("user__submissions", filter=Q(user__submissions__classroom=classroom)),
                flagged=Count(
                    "user__submissions",
                    filter=Q(user__submissions__classroom=classroom, user__submissions__final_verdict__in=FLAGGED_VERDICTS),
                ),
                last_submission_at=Max("user__submissions__created_at", filter=Q(user__submissions__classroom=classroom)),
            )
        )
        return Response(MemberSerializer(members, many=True).data)

    @action(detail=True, methods=["delete"], url_path=r"members/(?P<user_id>\d+)")
    def remove_member(self, request, id=None, user_id=None):
        classroom = self._owned()
        deleted, _ = Membership.objects.filter(classroom=classroom, user_id=user_id).delete()
        if not deleted:
            raise NotFound("Not a member.")
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def leave(self, request, id=None):
        classroom = self.get_object()
        if classroom.owner_id == request.user.id:
            return Response({"detail": "The teacher cannot leave; archive the class instead."}, status=status.HTTP_400_BAD_REQUEST)
        Membership.objects.filter(classroom=classroom, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _class_submissions(self, classroom):
        qs = Submission.objects.filter(classroom=classroom).select_related("user", "uploaded_by", "plagiarism_report").prefetch_related("analysis_results__analyzer")
        if not can_supervise(classroom, self.request.user):
            return qs.filter(user=self.request.user)
        params = self.request.query_params
        if params.get("student"):
            qs = qs.filter(user_id=params["student"])
        if params.get("verdict") == "flagged":
            qs = qs.filter(final_verdict__in=FLAGGED_VERDICTS)
        elif params.get("verdict"):
            qs = qs.filter(final_verdict=params["verdict"])
        return qs

    @action(detail=True, methods=["get"])
    def submissions(self, request, id=None):
        classroom = self.get_object()
        qs = self._class_submissions(classroom).order_by("-created_at")[:500]
        return Response(ClassSubmissionSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def stats(self, request, id=None):
        classroom = self._owned()
        qs = Submission.objects.filter(classroom=classroom)
        total = qs.count()
        completed = qs.filter(status=Submission.Status.COMPLETED)
        flagged = completed.filter(final_verdict__in=FLAGGED_VERDICTS).count()
        by_verdict = dict(completed.exclude(final_verdict="").values_list("final_verdict").annotate(c=Count("id")))
        since = timezone.now() - timedelta(days=TIMELINE_DAYS)
        timeline = [
            {"date": row["day"].isoformat(), "total": row["total"], "flagged": row["flagged"]}
            for row in qs.filter(created_at__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"), flagged=Count("id", filter=Q(final_verdict__in=FLAGGED_VERDICTS)))
            .order_by("day")
        ]
        return Response({
            "students": Membership.objects.filter(classroom=classroom).count(),
            "total": total,
            "completed": completed.count(),
            "flagged": flagged,
            "flagged_share": round(flagged / completed.count(), 4) if completed.exists() else 0.0,
            "by_verdict": by_verdict,
            "timeline": timeline,
        })

    @action(detail=True, methods=["get"])
    def radar(self, request, id=None):
        classroom = self._owned()
        try:
            days = min(RADAR_MAX_DAYS, max(1, int(request.query_params.get("days", RADAR_DAYS))))
        except ValueError:
            days = RADAR_DAYS
        return Response({"days": days, **class_radar(classroom, timezone.now() - timedelta(days=days))})

    @action(detail=True, methods=["get", "post"])
    def shadows(self, request, id=None):
        classroom = self._owned()
        if request.method == "GET":
            sets = ShadowSet.objects.filter(classroom=classroom).annotate(answer_count=Count("answers"))[:50]
            return Response(ShadowSetSerializer(sets, many=True).data)
        if sets_today(classroom) >= DAILY_SETS:
            return Response({"detail": f"Up to {DAILY_SETS} shadow sets per class per day."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        serializer = ShadowSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prompt = serializer.validated_data["prompt"]
        shadow = ShadowSet.objects.create(
            classroom=classroom,
            created_by=request.user,
            prompt=prompt,
            language=prompt_language(prompt),
            target=serializer.validated_data["target"],
        )
        transaction.on_commit(lambda: build_shadow_set.delay(str(shadow.id)))
        return Response(ShadowSetSerializer(shadow).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "delete"], url_path=r"shadows/(?P<shadow_id>[0-9a-f-]+)")
    def shadow_detail(self, request, id=None, shadow_id=None):
        classroom = self._owned()
        shadow = ShadowSet.objects.filter(classroom=classroom, id=shadow_id).first()
        if shadow is None:
            raise NotFound("No such shadow set.")
        if request.method == "DELETE":
            shadow.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        answers = [{"variant": a.variant, "text": a.text} for a in shadow.answers.all()]
        return Response({**ShadowSetSerializer(shadow).data, "answers": len(answers), "texts": answers})

    @action(detail=True, methods=["get"], url_path="export.csv")
    def export_csv(self, request, id=None):
        classroom = self._owned()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(("student", "email", "submission_id", "original_filename", "status", "final_verdict", "final_score", "tribunal_version", "words", "originality", "created_at"))
        for s in Submission.objects.filter(classroom=classroom).select_related("user", "plagiarism_report").order_by("user__username", "-created_at"):
            words = ((s.metadata or {}).get("document") or {}).get("words")
            writer.writerow([
                csv_safe(s.user.username), csv_safe(s.user.email), csv_safe(s.id), csv_safe(s.original_filename),
                csv_safe(s.status), csv_safe(s.final_verdict),
                "" if s.final_score is None else f"{s.final_score:.4f}", csv_safe(s.tribunal_version),
                "" if words is None else words, _originality(s), s.created_at.isoformat(),
            ])
        response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="prooflayer_class_{classroom.id}.csv"'
        return response


class JoinClassroomView(APIView):
    permission_classes = [IsVerifiedUser]

    def post(self, request):
        code = (request.data.get("code") or "").strip().upper()
        classroom = Classroom.objects.filter(join_code=code, archived=False).select_related("owner").first()
        if classroom is None:
            return Response({"detail": "No active classroom with that code."}, status=status.HTTP_404_NOT_FOUND)
        if classroom.owner_id == request.user.id:
            return Response({"detail": "You teach this classroom."}, status=status.HTTP_400_BAD_REQUEST)
        _, created = Membership.objects.get_or_create(classroom=classroom, user=request.user)
        data = ClassroomSerializer(classroom, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
