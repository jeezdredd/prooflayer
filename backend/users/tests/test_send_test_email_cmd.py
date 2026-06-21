import pytest
from django.core.management import call_command
from django.test import override_settings

from users.models import EmailLog


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_test_email_command():
    call_command("send_test_email", "ops@example.com")
    log = EmailLog.objects.get(kind="test")
    assert log.to_email == "ops@example.com"
    assert log.status == "sent"
