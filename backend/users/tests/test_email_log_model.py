import pytest

from users.models import EmailLog
from users.tests.factories import UserFactory


@pytest.mark.django_db
def test_email_log_create_defaults():
    user = UserFactory()
    log = EmailLog.objects.create(
        to_email="x@example.com",
        kind="verification",
        subject="Verify",
        backend="resend",
        status="sent",
        user=user,
    )
    assert log.created_at is not None
    assert log.error == ""
    assert str(log) == "verification sent x@example.com"


@pytest.mark.django_db
def test_email_log_user_nullable_on_delete():
    user = UserFactory()
    log = EmailLog.objects.create(
        to_email="y@example.com", kind="test", backend="console", status="console", user=user
    )
    user.delete()
    log.refresh_from_db()
    assert log.user is None
