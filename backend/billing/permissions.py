from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission

from billing.models import get_or_create_subscription


class UpgradeRequired(APIException):
    status_code = 402
    default_code = "upgrade_required"

    def __init__(self, feature: str):
        super().__init__(detail={"detail": f"{feature} requires a higher plan.", "code": "upgrade_required", "feature": feature})


def tier_allows(user, flag: str) -> bool:
    if not (user and user.is_authenticated):
        return False
    if user.is_staff or user.is_superuser:
        return True
    sub = get_or_create_subscription(user)
    return sub.is_active and bool(getattr(sub, flag, False))


class HasTierFeature(BasePermission):
    """Allow only users whose active plan grants `flag` (a Subscription property). Staff always pass.

    Raises 402 rather than 403 so the frontend can show an upgrade prompt.
    """

    flag = ""
    feature = ""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if tier_allows(request.user, self.flag):
            return True
        raise UpgradeRequired(self.feature or self.flag)


def tier_feature(flag: str, feature: str) -> type[HasTierFeature]:
    return type(f"Has_{flag}", (HasTierFeature,), {"flag": flag, "feature": feature})


CanCompare = tier_feature("can_compare", "Compare")
CanUseApi = tier_feature("can_api", "API access")
