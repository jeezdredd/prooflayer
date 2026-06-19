from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


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
