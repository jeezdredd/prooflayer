from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from billing.permissions import tier_allows

from .models import Classroom, Membership


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
        classroom = Classroom.objects.select_related("owner").get(id=classroom_id)
    except (Classroom.DoesNotExist, ValueError, ValidationError) as exc:
        raise NotFound("Classroom not found.") from exc
    if classroom.owner_id != user.id and not is_member(classroom, user):
        raise NotFound("Classroom not found.")
    if classroom.archived:
        raise ValidationError({"classroom": ["This classroom is archived."]})
    if not tier_allows(classroom.owner, "can_classroom"):
        raise PermissionDenied("The teacher's Education plan is not active; uploads to this class are paused.")
    return classroom


def quota_owner(user, classroom: Classroom | None):
    return classroom.owner if classroom else user
