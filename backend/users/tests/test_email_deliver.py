from unittest.mock import patch

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from users.emails import deliver
from users.models import EmailLog


def _msg():
    return EmailMultiAlternatives(subject="Hi", body="b", from_email="f@x.com", to=["to@x.com"])


@pytest.mark.django_db
@override_settings(
    EMAIL_CONFIGURED=True,
    EMAIL_MODE="resend",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
def test_deliver_sent_when_configured():
    status = deliver(_msg(), kind="verification")
    assert status == "sent"
    assert len(mail.outbox) == 1
    log = EmailLog.objects.get()
    assert log.status == "sent"
    assert log.backend == "resend"
    assert log.to_email == "to@x.com"


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_deliver_console_when_unconfigured():
    status = deliver(_msg(), kind="verification")
    assert status == "console"
    assert EmailLog.objects.get().status == "console"


@pytest.mark.django_db
@override_settings(
    EMAIL_CONFIGURED=True,
    EMAIL_MODE="smtp",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
def test_deliver_smtp_mode():
    status = deliver(_msg(), kind="verification")
    assert status == "sent"
    assert len(mail.outbox) == 1
    log = EmailLog.objects.get()
    assert log.status == "sent"
    assert log.backend == "smtp"


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True)
def test_deliver_failed_reraises_and_logs():
    with patch.object(EmailMultiAlternatives, "send", side_effect=RuntimeError("smtp down")):
        with pytest.raises(RuntimeError):
            deliver(_msg(), kind="verification")
    log = EmailLog.objects.get()
    assert log.status == "failed"
    assert "smtp down" in log.error


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_log_write_failure_does_not_break_send():
    with patch("users.emails.EmailLog.objects.create", side_effect=Exception("db gone")):
        status = deliver(_msg(), kind="verification")
    assert status == "sent"
    assert len(mail.outbox) == 1
