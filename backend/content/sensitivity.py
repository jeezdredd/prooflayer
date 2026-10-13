from rest_framework.exceptions import AuthenticationFailed
from rest_framework.settings import api_settings

from common.age import can_view_sensitive

from .models import Submission

ADULT_REQUIRED_DETAIL = "Publishing to the public feed is available from age 18."
ADULT_REQUIRED_CODE = "adult_required"

TRUTHY = {True, 1, "1", "true", "True", "on", "yes"}
FALSY = {False, 0, "0", "false", "False", "off", "no", ""}


def for_viewer(queryset, user):
    if can_view_sensitive(user):
        return queryset
    return queryset.exclude(is_sensitive=True)


def parse_flag(value):
    if not isinstance(value, (bool, int, str)):
        return None
    if value in TRUTHY:
        return True
    if value in FALSY:
        return False
    return None


class OptionalViewerAuthentication:
    def __init__(self):
        self._authenticators = [cls() for cls in api_settings.DEFAULT_AUTHENTICATION_CLASSES]

    def authenticate(self, request):
        for authenticator in self._authenticators:
            try:
                result = authenticator.authenticate(request)
            except AuthenticationFailed:
                return None
            if result is not None:
                return result
        return None

    def authenticate_header(self, request):
        return None


def unpublish_all(user) -> int:
    return Submission.objects.filter(user=user, is_public=True).update(is_public=False)
