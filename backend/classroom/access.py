from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from billing.models import Subscription
from billing.permissions import tier_allows
from content.models import Submission

from .models import Classroom, Membership, OrgMember

STUDENT_ONLY_DETAIL = "Student accounts hand in work through their class. ProofLayer tools are for teachers."
STUDENT_ONLY_CODE = "student_account"


def is_student_only(user) -> bool:
    if not getattr(user, "is_authenticated", False) or user.is_staff:
        return False
    if not Membership.objects.filter(user=user).exists():
        return False
    if Classroom.objects.filter(owner=user).exists() or OrgMember.objects.filter(user=user).exists():
        return False
    tier = Subscription.objects.filter(user=user).values_list("tier", flat=True).first()
    return tier in (None, Subscription.Tier.FREE)


def deny_student_only(user):
    if is_student_only(user):
        raise PermissionDenied({"detail": STUDENT_ONLY_DETAIL, "code": STUDENT_ONLY_CODE})


class NotStudentAccount(BasePermission):
    message = {"detail": STUDENT_ONLY_DETAIL, "code": STUDENT_ONLY_CODE}

    def has_permission(self, request, view):
        return not is_student_only(request.user)


def supervised_q(user, prefix: str = "") -> Q:
    return Q(**{f"{prefix}owner": user}) | Q(**{
        f"{prefix}organization__members__user": user,
        f"{prefix}organization__members__role": OrgMember.Role.ADMIN,
    })


def can_supervise(classroom: Classroom, user) -> bool:
    if classroom.owner_id == user.id:
        return True
    return bool(classroom.organization_id) and OrgMember.objects.filter(
        organization_id=classroom.organization_id, user=user, role=OrgMember.Role.ADMIN,
    ).exists()


def visible_submissions_q(user) -> Q:
    return Q(user=user) | supervised_q(user, prefix="classroom__")


def can_view_submission(user, submission_id) -> bool:
    if user.is_staff:
        return Submission.objects.filter(id=submission_id).exists()
    return Submission.objects.filter(visible_submissions_q(user), id=submission_id).exists()


def is_member(classroom: Classroom, user) -> bool:
    return Membership.objects.filter(classroom=classroom, user=user).exists()


def classroom_for_upload(user, classroom_id) -> Classroom | None:
    """The classroom a student (or the teacher) is uploading into, or None for a personal upload.

    Uploads into a class are charged to the owner's Education plan, so the owner must still hold
    it; otherwise a lapsed teacher plan would silently start billing students.
    """
    if not classroom_id:
        return None
    try:
        classroom = Classroom.objects.select_related("owner", "organization__owner").get(id=classroom_id)
    except (Classroom.DoesNotExist, ValueError, ValidationError) as exc:
        raise NotFound("Classroom not found.") from exc
    if classroom.owner_id != user.id and not is_member(classroom, user):
        raise NotFound("Classroom not found.")
    if classroom.archived:
        raise ValidationError({"classroom": ["This classroom is archived."]})
    if not tier_allows(classroom.billing_owner, "can_classroom"):
        raise PermissionDenied("The Education plan behind this class is not active; uploads are paused.")
    return classroom


def quota_owner(user, classroom: Classroom | None):
    return classroom.billing_owner if classroom else user
