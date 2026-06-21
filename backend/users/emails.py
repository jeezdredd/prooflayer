import logging

from django.conf import settings

from .models import EmailLog

logger = logging.getLogger(__name__)


def _safe_log(to_email, subject, kind, backend, status, error, user):
    try:
        EmailLog.objects.create(
            to_email=to_email or "",
            subject=(subject or "")[:255],
            kind=kind,
            backend=backend,
            status=status,
            error=error or "",
            user=user,
        )
    except Exception as exc:
        logger.warning("EmailLog write failed (%s): %s", status, exc)


def deliver(msg, *, kind, user=None) -> str:
    configured = bool(getattr(settings, "EMAIL_CONFIGURED", False))
    backend = "resend" if configured else "console"
    to_email = (msg.to or [""])[0]
    try:
        msg.send(fail_silently=False)
    except Exception as exc:
        _safe_log(to_email, msg.subject, kind, backend, "failed", str(exc)[:2000], user)
        raise
    status = "sent" if configured else "console"
    _safe_log(to_email, msg.subject, kind, backend, status, "", user)
    return status
