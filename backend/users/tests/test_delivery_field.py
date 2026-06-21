import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from users.tests.factories import UserFactory


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_register_includes_delivery():
    client = APIClient()
    resp = client.post(
        reverse("register"),
        {
            "email": "new@example.com",
            "username": "newuser",
            "password": "Str0ngPass!23",
            "password_confirm": "Str0ngPass!23",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["delivery"] == "email"


@pytest.mark.django_db
@override_settings(EMAIL_CONFIGURED=False)
def test_resend_includes_console_delivery():
    user = UserFactory(is_verified=False)
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(reverse("resend-verification"))
    assert resp.status_code == 200
    assert resp.data["delivery"] == "console"
