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

from analyzers.models import AnalysisResult
from billing.permissions import tier_feature
from common.names import display_name, save_name
from content.models import Batch, Submission
from users.permissions import IsVerifiedUser

from .access import can_supervise, supervised_q
from .attention import FLAGGED, attention_q, class_attention
from .export import class_table, pick_lang
from .models import Classroom, Membership, ShadowSet
from .radar import class_radar
from .serializers import (
    ClassroomSerializer,
    ClassSubmissionSerializer,
    MemberSerializer,
    ShadowSetSerializer,
    class_context,
    is_unattributed,
)
from .shadow import DAILY_SETS, prompt_language, sets_today
from .tasks import build_shadow_set

TIMELINE_DAYS = 30
RADAR_DAYS = 60
RADAR_MAX_DAYS = 365
CanCreateClassroom = tier_feature("can_classroom", "Classroom")


def class_rows(queryset):
    return (
        queryset.select_related("user", "uploaded_by", "plagiarism_report")
        .prefetch_related("analysis_results__analyzer", "objections")
    )


def shadow_reach(classroom, sets) -> dict:
    results = list(
        AnalysisResult.objects.filter(
            analyzer__name="text_shadow", submission__classroom=classroom, evidence__has_key="share",
        ).select_related("submission__user")
    )
    reach = {}
    for shadow in sets:
        compared = 0
        matched = []
        for result in results:
            if result.submission.created_at < shadow.created_at:
                continue
            compared += 1
            evidence = result.evidence if isinstance(result.evidence, dict) else {}
            if result.verdict in FLAGGED and evidence.get("shadow_set") == str(shadow.id):
                matched.append({
                    "submission_id": str(result.submission_id),
                    "student": display_name(result.submission.user),
                    "filename": result.submission.original_filename,
                })
        reach[shadow.id] = {"compared": compared, "matched": matched}
    return reach


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

    def list(self, request, *args, **kwargs):
        classes = list(self.get_queryset())
        context = {**self.get_serializer_context(), "attention": class_attention(c.pk for c in classes)}
        return Response(ClassroomSerializer(classes, many=True, context=context).data)

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
        members = list(Membership.objects.filter(classroom=classroom).select_related("user"))
        works = Submission.objects.filter(classroom=classroom).order_by()
        totals = dict(works.values_list("user_id").annotate(n=Count("id")))
        flagged = dict(works.filter(attention_q()).values_list("user_id").annotate(n=Count("id")))
        latest = dict(works.values_list("user_id").annotate(at=Max("created_at")))
        for member in members:
            member.total = totals.get(member.user_id, 0)
            member.flagged = flagged.get(member.user_id, 0)
            member.last_submission_at = latest.get(member.user_id)
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
        qs = class_rows(Submission.objects.filter(classroom=classroom))
        if not can_supervise(classroom, self.request.user):
            return qs.filter(user=self.request.user)
        params = self.request.query_params
        if params.get("student"):
            qs = qs.filter(user_id=params["student"])
        if params.get("verdict") == "flagged":
            qs = qs.filter(attention_q())
        elif params.get("verdict"):
            qs = qs.filter(final_verdict=params["verdict"])
        return qs

    @action(detail=True, methods=["get"])
    def submissions(self, request, id=None):
        classroom = self.get_object()
        qs = self._class_submissions(classroom).order_by("-created_at")[:500]
        return Response(ClassSubmissionSerializer(qs, many=True, context=class_context(classroom)).data)

    @action(detail=True, methods=["get"])
    def stats(self, request, id=None):
        classroom = self._owned()
        qs = Submission.objects.filter(classroom=classroom)
        total = qs.count()
        completed = qs.filter(status=Submission.Status.COMPLETED)
        flagged = qs.filter(attention_q()).count()
        by_verdict = dict(
            completed.exclude(final_verdict="").order_by().values_list("final_verdict").annotate(c=Count("id"))
        )
        since = timezone.now() - timedelta(days=TIMELINE_DAYS)
        timeline = [
            {"date": row["day"].isoformat(), "total": row["total"], "flagged": row["flagged"]}
            for row in qs.filter(created_at__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"), flagged=Count("id", filter=attention_q()))
            .order_by("day")
        ]
        done = completed.count()
        return Response({
            "students": Membership.objects.filter(classroom=classroom).count(),
            "total": total,
            "completed": done,
            "flagged": flagged,
            "flagged_share": round(flagged / done, 4) if done else 0.0,
            "by_verdict": by_verdict,
            "timeline": timeline,
        })

    @action(detail=True, methods=["get"])
    def batches(self, request, id=None):
        classroom = self._owned()
        rows = list(
            Batch.objects.filter(classroom=classroom)
            .annotate(total=Count("submissions"))
            .order_by("-created_at")[:50]
        )
        flagged = dict(
            Submission.objects.filter(batch__in=rows).filter(attention_q())
            .order_by().values_list("batch_id").annotate(n=Count("id"))
        )
        return Response([
            {
                "id": str(b.id),
                "name": b.name,
                "created_at": b.created_at,
                "total": b.total,
                "flagged": flagged.get(b.id, 0),
            }
            for b in rows
        ])

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
            sets = list(ShadowSet.objects.filter(classroom=classroom).annotate(answer_count=Count("answers"))[:50])
            reach = shadow_reach(classroom, sets)
            return Response([{**ShadowSetSerializer(s).data, **reach[s.id]} for s in sets])
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
        context = class_context(classroom)
        rows = class_rows(Submission.objects.filter(classroom=classroom)).order_by(
            "user__last_name", "user__first_name", "user__username", "-created_at",
        )
        body = class_table(rows, pick_lang(request), lambda s: is_unattributed(s, context))
        response = HttpResponse(body, content_type="text/csv; charset=utf-8")
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
        save_name(request.user, request.data.get("name"))
        _, created = Membership.objects.get_or_create(classroom=classroom, user=request.user)
        data = ClassroomSerializer(classroom, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
