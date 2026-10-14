from unittest.mock import patch

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail as outbox
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from users.mail import split_body, unsubscribe_token
from users.models import ProductUpdate, ProductUpdateDelivery, User
from users.tasks import send_password_reset_email, send_product_update, send_verification_email

from .factories import UserFactory

LOCMEM = {"EMAIL_CONFIGURED": True, "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}


def _update():
    return ProductUpdate.objects.create(
        title_en="New detector",
        title_ru="Новый детектор",
        body_en="Intro line.\n\n- first\n- second",
        body_ru="Вступление.\n\n- первое\n- второе",
        cta_label_en="Open",
        cta_url="https://prooflayer.cloud/status",
    )


@pytest.mark.django_db
class TestPasswordReset:
    def setup_method(self):
        self.client = APIClient()

    def test_request_queues_email_for_existing_user_only(self):
        user = UserFactory(email="known@example.com")
        with patch("users.views.send_password_reset_email.delay") as delay:
            first = self.client.post(reverse("password-reset"), {"email": "KNOWN@example.com"}, format="json")
            second = self.client.post(reverse("password-reset"), {"email": "nobody@example.com"}, format="json")
        assert first.status_code == second.status_code == 200
        assert first.data == second.data
        delay.assert_called_once_with(user.id)

    def test_confirm_sets_password_and_revokes_sessions(self):
        user = UserFactory()
        refresh = RefreshToken.for_user(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        response = self.client.post(
            reverse("password-reset-confirm"),
            {"uid": uid, "token": token, "password": "Fresh-Pass-2026"},
            format="json",
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password("Fresh-Pass-2026")
        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()
        again = self.client.post(
            reverse("password-reset-confirm"),
            {"uid": uid, "token": token, "password": "Other-Pass-2026"},
            format="json",
        )
        assert again.status_code == 400

    def test_confirm_rejects_weak_password(self):
        user = UserFactory()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        response = self.client.post(reverse("password-reset-confirm"), {"uid": uid, "token": token, "password": "123"}, format="json")
        assert response.status_code == 400
        assert "password" in response.data

    def test_confirm_rejects_bad_uid(self):
        response = self.client.post(reverse("password-reset-confirm"), {"uid": "zzz", "token": "x", "password": "Fresh-Pass-2026"}, format="json")
        assert response.status_code == 400

    @override_settings(**LOCMEM)
    def test_reset_email_is_in_user_language(self):
        user = UserFactory(language="ru")
        send_password_reset_email(user.id)
        message = outbox.outbox[-1]
        assert message.subject == "Сброс пароля ProofLayer"
        assert "reset-password?uid=" in message.alternatives[0][0]


@pytest.mark.django_db
@override_settings(**LOCMEM)
def test_verification_email_uses_language_and_branding():
    user = UserFactory(language="en", is_verified=False)
    send_verification_email(user.id)
    message = outbox.outbox[-1]
    html = message.alternatives[0][0]
    assert message.subject == "Confirm your email for ProofLayer"
    assert "verify-email?token=" in html
    assert "email/wordmark.png" in html
    assert "verify-email?token=" in message.body


@pytest.mark.django_db
class TestUnsubscribe:
    def test_token_turns_updates_off(self):
        user = UserFactory()
        assert user.email_updates is True
        response = APIClient().post(reverse("unsubscribe"), {"token": unsubscribe_token(user)}, format="json")
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.email_updates is False

    def test_one_click_post_with_query_token(self):
        user = UserFactory()
        url = f"{reverse('unsubscribe')}?token={unsubscribe_token(user)}"
        response = APIClient().post(url, "List-Unsubscribe=One-Click", content_type="application/x-www-form-urlencoded")
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.email_updates is False

    def test_forged_token_rejected(self):
        response = APIClient().post(reverse("unsubscribe"), {"token": "forged"}, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestProductUpdate:
    @override_settings(**LOCMEM)
    def test_sends_once_to_verified_subscribers_in_their_language(self):
        ru = UserFactory(is_verified=True, language="ru")
        en = UserFactory(is_verified=True, language="en")
        UserFactory(is_verified=True, email_updates=False)
        UserFactory(is_verified=False)
        update = _update()
        with patch("users.tasks.time.sleep"):
            assert send_product_update(update.id) == 2
            assert send_product_update(update.id) == 0
        update.refresh_from_db()
        assert update.status == ProductUpdate.Status.SENT
        assert update.recipients == 2
        subjects = {m.to[0]: m.subject for m in outbox.outbox}
        assert subjects == {ru.email: "Новый детектор", en.email: "New detector"}
        assert set(ProductUpdateDelivery.objects.values_list("user_id", flat=True)) == {ru.id, en.id}
        message = next(m for m in outbox.outbox if m.to[0] == en.email)
        assert message.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert "unsubscribe?token=" in message.alternatives[0][0]


def test_split_body_makes_paragraphs_and_lists():
    assert split_body("One\ntwo\n\n- a\n- b\n\nEnd") == [{"text": "One two"}, {"list": ["a", "b"]}, {"text": "End"}]


@pytest.mark.django_db
def test_register_stores_language():
    response = APIClient().post(
        reverse("register"),
        {"email": "lang@example.com", "username": "lang", "password": "StrongPass123!", "password_confirm": "StrongPass123!", "accept_terms": True, "language": "ru"},
        format="json",
    )
    assert response.status_code == 201
    assert User.objects.get(email="lang@example.com").language == "ru"
