from django.conf import settings

from classroom.access import can_supervise, is_student_only
from common.names import display_name

AUTHOR = "author"
SUPERVISOR = "supervisor"
VIEWER = "viewer"


def _authenticated(user) -> bool:
    return user is not None and getattr(user, "is_authenticated", False)


def supervises_class(submission, user) -> bool:
    if not _authenticated(user) or submission.classroom_id is None:
        return False
    return can_supervise(submission.classroom, user)


def viewer_info(submission, user) -> dict:
    authed = _authenticated(user)
    author = authed and submission.user_id == user.id
    supervises = supervises_class(submission, user)
    role = AUTHOR if author else SUPERVISOR if supervises else VIEWER
    sees_class = role != VIEWER or (authed and user.is_staff)
    classroom = submission.classroom if submission.classroom_id and sees_class else None
    return {
        "role": role,
        "supervises": supervises,
        "student_view": author and submission.classroom_id is not None and not supervises,
        "can_object": author and not supervises,
        "can_publish": author and submission.classroom_id is None and not is_student_only(user),
        "student_name": display_name(submission.user) if role != VIEWER else None,
        "classroom": {
            "id": str(classroom.id),
            "name": classroom.name,
            "organization_slug": classroom.organization.slug if classroom.organization_id else None,
        } if classroom is not None else None,
    }


def result_url(submission) -> str:
    base = getattr(settings, "CLASSROOM_URL", "") if submission.classroom_id else ""
    return f"{(base or settings.FRONTEND_URL).rstrip('/')}/results/{submission.id}"
