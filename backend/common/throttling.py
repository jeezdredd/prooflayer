from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

from users.models import ApiKey


class StaffBypassUserRateThrottle(UserRateThrottle):
    def allow_request(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return True
        return super().allow_request(request, view)


class StaffBypassAnonRateThrottle(AnonRateThrottle):
    def allow_request(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return True
        return super().allow_request(request, view)


class ApiKeyRateThrottle(SimpleRateThrottle):
    """Per-key budget for requests authenticated with an API key; no-op for browser sessions."""

    scope = "api"

    def get_cache_key(self, request, view):
        key = getattr(request, "auth", None)
        if not isinstance(key, ApiKey):
            return None
        return self.cache_format % {"scope": self.scope, "ident": f"key:{key.pk}"}
