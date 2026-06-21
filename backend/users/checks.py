from django.conf import settings
from django.core.checks import Warning, register


@register()
def email_backend_check(app_configs, **kwargs):
    if not settings.DEBUG and not getattr(settings, "EMAIL_CONFIGURED", False):
        return [
            Warning(
                "Email backend not configured (no RESEND_API_KEY). Verification emails "
                "fall back to the console backend and are not delivered.",
                id="users.W001",
            )
        ]
    return []
