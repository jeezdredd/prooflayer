import re

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import get_or_create_subscription
from billing.permissions import tier_allows
from content.models import Batch, Submission
from users.permissions import IsVerifiedUser

from .models import RESERVED_SLUGS, SLUG_PATTERN, Classroom, Membership, Organization, OrgMember
from .serializers import ClassroomSerializer


def _org(slug: str) -> Organization:
    org = Organization.objects.select_related("owner").filter(slug=(slug or "").lower()).first()
    if org is None:
        raise NotFound("No such organization.")
    return org


def _role(org: Organization, user) -> str | None:
    if not (user and user.is_authenticated):
        return None
    member = OrgMember.objects.filter(organization=org, user=user).first()
    if member:
        return member.role
    if Membership.objects.filter(classroom__organization=org, user=user).exists():
        return "student"
    return None


def _require_admin(org, user):
    if _role(org, user) != OrgMember.Role.ADMIN:
        raise PermissionDenied("Only the organization admin can do this.")


def _owner_plan(owner):
    return None if owner.is_staff else get_or_create_subscription(owner).plan


def org_payload(org: Organization, user) -> dict:
    role = _role(org, user)
    data = {"name": org.name, "slug": org.slug, "role": role}
    if role == OrgMember.Role.ADMIN:
        data["teacher_code"] = org.teacher_code
        data["plan_active"] = tier_allows(org.owner, "can_classroom")
        plan = _owner_plan(org.owner)
        data["teacher_seats"] = plan.teacher_seats if plan else None
        data["teacher_seats_used"] = OrgMember.objects.filter(organization__owner=org.owner).values("user").distinct().count()
    return data


def parse_level(raw) -> int | None:
    if raw in (None, ""):
        return None
    try:
        level = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"level": ["Must be 1-11 for a school year or 12-17 for university years 1-6."]}) from exc
    if not 1 <= level <= 17:
        raise ValidationError({"level": ["Must be 1-11 for a school year or 12-17 for university years 1-6."]})
    return level


def validate_slug(raw: str) -> str:
    slug = (raw or "").strip().lower()
    if not re.match(SLUG_PATTERN, slug):
        raise ValidationError({"slug": ["3-40 characters: lowercase letters, digits and hyphens, not at the ends."]})
    if slug in RESERVED_SLUGS:
        raise ValidationError({"slug": ["That address is reserved."]})
    if Organization.objects.filter(slug=slug).exists():
        raise ValidationError({"slug": ["That address is taken."]})
    return slug


class OrganizationListView(APIView):
    def get_permissions(self):
        return [IsVerifiedUser()] if self.request.method == "POST" else [IsAuthenticated()]

    def get(self, request):
        orgs = Organization.objects.filter(members__user=request.user).select_related("owner").distinct()
        return Response([org_payload(o, request.user) for o in orgs])

    def post(self, request):
        if not tier_allows(request.user, "can_classroom"):
            return Response(
                {"detail": "Creating an organization needs the Education plan.", "code": "upgrade_required"},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        plan = _owner_plan(request.user)
        if plan and Organization.objects.filter(owner=request.user).count() >= plan.schools:
            return Response(
                {
                    "detail": f"The {plan.name} plan includes {plan.schools} school address{'es' if plan.schools != 1 else ''}. University includes 10.",
                    "code": "upgrade_required",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        name = (request.data.get("name") or "").strip()[:120]
        if not name:
            raise ValidationError({"name": ["Required."]})
        org = Organization.create_for(request.user, name, validate_slug(request.data.get("slug")))
        return Response(org_payload(org, request.user), status=status.HTTP_201_CREATED)


class OrganizationDetailView(APIView):
    """Public by slug so classroom.prooflayer.cloud/<slug> can show the school name before login."""

    permission_classes = [AllowAny]

    def get(self, request, slug):
        return Response(org_payload(_org(slug), request.user))

    def delete(self, request, slug):
        org = _org(slug)
        if not request.user.is_authenticated or org.owner_id != request.user.id:
            raise PermissionDenied("Only the owner can delete the school.")
        if not request.user.check_password(request.data.get("password") or ""):
            raise PermissionDenied("Password is incorrect.")
        with transaction.atomic():
            for submission in Submission.objects.filter(classroom__organization=org).iterator(chunk_size=200):
                if submission.file:
                    submission.file.delete(save=False)
                if submission.thumbnail:
                    submission.thumbnail.delete(save=False)
            Submission.objects.filter(classroom__organization=org).delete()
            Batch.objects.filter(classroom__organization=org).delete()
            org.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationJoinTeacherView(APIView):
    permission_classes = [IsVerifiedUser]

    def post(self, request, slug):
        org = _org(slug)
        if (request.data.get("code") or "").strip().upper() != org.teacher_code:
            raise NotFound("Wrong teacher code.")
        plan = _owner_plan(org.owner)
        already_seated = OrgMember.objects.filter(organization__owner=org.owner, user=request.user).exists()
        if plan and not already_seated:
            used = OrgMember.objects.filter(organization__owner=org.owner).values("user").distinct().count()
            if used >= plan.teacher_seats:
                raise PermissionDenied(
                    f"All {plan.teacher_seats} teacher seats on this school's {plan.name} plan are taken. Ask the admin to free one or upgrade."
                )
        _, created = OrgMember.objects.get_or_create(organization=org, user=request.user, defaults={"role": OrgMember.Role.TEACHER})
        return Response(org_payload(org, request.user), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class OrganizationRotateCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        org = _org(slug)
        _require_admin(org, request.user)
        return Response({"teacher_code": org.rotate_teacher_code()})


class OrganizationTeachersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        org = _org(slug)
        _require_admin(org, request.user)
        members = OrgMember.objects.filter(organization=org).select_related("user").annotate(
            classes=Count("user__owned_classrooms", filter=Q(user__owned_classrooms__organization=org)),
        )
        return Response([
            {"user_id": m.user_id, "username": m.user.username, "email": m.user.email, "role": m.role,
             "classes": m.classes, "joined_at": m.joined_at}
            for m in members
        ])

    def delete(self, request, slug, user_id):
        org = _org(slug)
        _require_admin(org, request.user)
        if int(user_id) == org.owner_id:
            raise ValidationError({"detail": "The owner cannot be removed."})
        deleted, _ = OrgMember.objects.filter(organization=org, user_id=user_id).delete()
        if not deleted:
            raise NotFound("Not a teacher here.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationClassesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        org = _org(slug)
        role = _role(org, request.user)
        qs = Classroom.objects.filter(organization=org).select_related("owner", "organization")
        if role == OrgMember.Role.ADMIN:
            pass
        elif role == OrgMember.Role.TEACHER:
            qs = qs.filter(owner=request.user)
        elif role == "student":
            qs = qs.filter(memberships__user=request.user)
        else:
            raise NotFound("No such organization.")
        qs = qs.annotate(student_count=Count("memberships", distinct=True)).distinct()
        return Response(ClassroomSerializer(qs, many=True, context={"request": request}).data)

    def post(self, request, slug):
        org = _org(slug)
        if _role(org, request.user) not in (OrgMember.Role.ADMIN, OrgMember.Role.TEACHER):
            raise PermissionDenied("Only teachers of this organization can create classes.")
        if not tier_allows(org.owner, "can_classroom"):
            raise PermissionDenied("The organization's Education plan is not active.")
        name = (request.data.get("name") or "").strip()[:120]
        if not name:
            raise ValidationError({"name": ["Required."]})
        classroom = Classroom.create_for(request.user, name, organization=org, level=parse_level(request.data.get("level")))
        classroom.student_count = 0
        return Response(ClassroomSerializer(classroom, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ClassroomHubView(APIView):
    """Everything the signed-in user has in Classroom, for the subdomain's home page."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        orgs = Organization.objects.filter(members__user=user).select_related("owner").distinct()
        enrolled = (
            Classroom.objects.filter(memberships__user=user, archived=False)
            .select_related("owner", "organization")
            .annotate(student_count=Count("memberships", distinct=True))
            .distinct()
        )
        personal = (
            Classroom.objects.filter(owner=user, organization__isnull=True)
            .select_related("owner")
            .annotate(student_count=Count("memberships", distinct=True))
        )
        ctx = {"request": request}
        return Response({
            "organizations": [org_payload(o, user) for o in orgs],
            "enrolled": ClassroomSerializer(enrolled, many=True, context=ctx).data,
            "personal_classes": ClassroomSerializer(personal, many=True, context=ctx).data,
            "can_create_organization": tier_allows(user, "can_classroom"),
        })
