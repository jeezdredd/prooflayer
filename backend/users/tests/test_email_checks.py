from django.test import override_settings

from users.checks import email_backend_check


@override_settings(DEBUG=False, EMAIL_CONFIGURED=False)
def test_warns_when_prod_unconfigured():
    results = email_backend_check(None)
    assert any(w.id == "users.W001" for w in results)


@override_settings(DEBUG=False, EMAIL_CONFIGURED=True)
def test_silent_when_configured():
    assert email_backend_check(None) == []


@override_settings(DEBUG=True, EMAIL_CONFIGURED=False)
def test_silent_in_dev():
    assert email_backend_check(None) == []
