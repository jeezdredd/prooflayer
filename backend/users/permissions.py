from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user


class IsVerifiedUser(BasePermission):
    message = "Email verification required."

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.is_superuser or u.is_staff:
            return True
        return bool(getattr(u, "is_verified", False))
