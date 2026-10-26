from rest_framework.exceptions import PermissionDenied

DEMO_DOMAIN = "demo.prooflayer.cloud"
DEMO_CODE = "demo_account"
DEMO_MESSAGE = "This is a shared demo account, so this is turned off."
DEMO_SCHOOL_CODE = "demo_school"
DEMO_SCHOOL_MESSAGE = "This is a demo school. Only its demo accounts can join it."
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def is_demo_email(email) -> bool:
    return (email or "").strip().lower().endswith(f"@{DEMO_DOMAIN}")


def is_demo(user) -> bool:
    return bool(user is not None and getattr(user, "is_authenticated", False) and is_demo_email(user.email))


class DemoAccountLocked(PermissionDenied):
    default_code = DEMO_CODE

    def __init__(self):
        super().__init__({"detail": DEMO_MESSAGE, "code": DEMO_CODE})


class DemoSchoolLocked(PermissionDenied):
    default_code = DEMO_SCHOOL_CODE

    def __init__(self):
        super().__init__({"detail": DEMO_SCHOOL_MESSAGE, "code": DEMO_SCHOOL_CODE})


def refuse_demo(user) -> None:
    if is_demo(user):
        raise DemoAccountLocked()


def refuse_demo_mixing(owner, user) -> None:
    demo_owner = is_demo_email(getattr(owner, "email", ""))
    if is_demo(user) and not demo_owner:
        raise DemoAccountLocked()
    if demo_owner and not is_demo(user):
        raise DemoSchoolLocked()


class DemoLockedWritesMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in SAFE_METHODS:
            refuse_demo(request.user)
