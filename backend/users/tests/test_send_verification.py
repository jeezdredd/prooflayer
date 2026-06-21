import pytest
from django.test import override_settings

from users.models import EmailLog, EmailVerificationToken
from users.tasks import send_verification_email
from users.tests.factories import UserFactory


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_verification_writes_log():
    user = UserFactory(is_verified=False)
    result = send_verification_email(user.id)
    assert result == "sent"
    assert EmailLog.objects.filter(kind="verification", to_email=user.email).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_verification_reuses_valid_token():
    user = UserFactory(is_verified=False)
    send_verification_email(user.id)
    send_verification_email(user.id)
    assert EmailVerificationToken.objects.filter(user=user).count() == 1


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_verification_skips_verified():
    user = UserFactory(is_verified=True)
    assert send_verification_email(user.id) == "already_verified"
