from datetime import timedelta

from django.utils import timezone
from rest_framework import authentication, exceptions

from billing.permissions import tier_allows

from .models import ApiKey

HEADER_SCHEME = "api-key"
LAST_USED_RESOLUTION = timedelta(minutes=1)


def _raw_key_from(request) -> str | None:
    header = authentication.get_authorization_header(request).decode("latin-1").strip()
    if header:
        scheme, _, value = header.partition(" ")
        if scheme.lower() == HEADER_SCHEME and value.strip():
            return value.strip()
        return None
    explicit = request.META.get("HTTP_X_API_KEY", "").strip()
    return explicit or None


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """`Authorization: Api-Key pl_...` or `X-API-Key: pl_...`. Sets request.auth to the ApiKey."""

    def authenticate(self, request):
        raw = _raw_key_from(request)
        if raw is None:
            return None
        key = ApiKey.lookup(raw)
        if key is None or not key.is_active:
            raise exceptions.AuthenticationFailed("Invalid or revoked API key.")
        user = key.user
        if not user.is_active:
            raise exceptions.AuthenticationFailed("Account disabled.")
        if not tier_allows(user, "can_api"):
            raise exceptions.AuthenticationFailed("API access is not included in your current plan.")
        now = timezone.now()
        if key.last_used_at is None or now - key.last_used_at > LAST_USED_RESOLUTION:
            ApiKey.objects.filter(pk=key.pk).update(last_used_at=now)
        return user, key

    def authenticate_header(self, request):
        return "Api-Key"
