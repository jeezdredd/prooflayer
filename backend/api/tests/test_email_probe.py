import pytest
from django.test import override_settings

from api.system_views import _probe_email
from users.models import EmailLog


@override_settings(DEBUG=True, EMAIL_CONFIGURED=False)
def test_probe_skip_in_dev():
    out = _probe_email()
    assert out["status"] == "skip"
    assert "to_email" not in out


@override_settings(DEBUG=False, EMAIL_CONFIGURED=False)
def test_probe_down_in_prod_unconfigured():
    assert _probe_email()["status"] == "down"


@pytest.mark.django_db
@override_settings(DEBUG=False, EMAIL_CONFIGURED=True)
def test_probe_ok_when_configured_and_clean():
    assert _probe_email()["status"] == "ok"


@pytest.mark.django_db
@override_settings(DEBUG=False, EMAIL_CONFIGURED=True)
def test_probe_down_when_recent_console_or_failed():
    EmailLog.objects.create(to_email="a@x.com", kind="verification", backend="console", status="console")
    out = _probe_email()
    assert out["status"] == "down"
    assert out["recent_failures"] == 1
