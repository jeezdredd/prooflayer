def can_view_sensitive(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_staff or user.is_superuser or getattr(user, "is_adult", False))
