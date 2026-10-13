from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from billing.permissions import tier_allows
from content.models import Submission

from .models import Classroom, Membership, OrgMember


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
