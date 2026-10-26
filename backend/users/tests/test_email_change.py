import threading
import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail as outbox
from django.core.cache import cache
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from users import views as user_views
from users.models import ApiKey, EmailChangeToken, EmailVerificationToken, User

from .factories import UserFactory

PASSWORD = "testpass123"
NEW = "new@example.com"


@pytest.fixture(autouse=True)
def _locmem_mail(settings):
    settings.EMAIL_CONFIGURED = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    outbox.outbox = []


@pytest.fixture(autouse=True)
def _private_cache(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "email-change-tests"}}
    cache.clear()


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _request(user, new_email=NEW, password=PASSWORD):
    return _client(user).post(reverse("email-change"), {"new_email": new_email, "password": password}, format="json")


def _confirm(token):
    return APIClient().post(reverse("email-change-confirm"), {"token": token}, format="json")


def _token(user):
    return EmailChangeToken.objects.filter(user=user).order_by("-created_at").first()


def _sent_to(address):
    return [m for m in outbox.outbox if m.to == [address]]


@pytest.mark.django_db
class TestRequest:
    def test_link_goes_to_new_address_and_notice_to_old(self):
        user = UserFactory(email="old@example.com", is_verified=True)
        response = _request(user)
        assert response.status_code == 202
        assert response.data["pending_email"] == NEW
        user.refresh_from_db()
        assert user.email == "old@example.com"
        change = _token(user)
        [confirm] = _sent_to(NEW)
        [notice] = _sent_to("old@example.com")
        assert confirm.subject == "Confirm your new email for ProofLayer"
        assert f"/confirm-email?token={change.token}" in confirm.body
        assert f"/confirm-email?token={change.token}" in confirm.alternatives[0][0]
        assert notice.subject == "Email change requested for your ProofLayer account"
        assert "n***@example.com" in notice.body
        assert NEW not in notice.body
        assert change.token not in notice.body

    def test_unverified_old_address_still_gets_the_notice(self):
        user = UserFactory(email="old@example.com", is_verified=False)
        assert _request(user).status_code == 202
        assert len(_sent_to("old@example.com")) == 1
        assert len(_sent_to(NEW)) == 1

    def test_mails_follow_the_account_language(self):
        user = UserFactory(email="old@example.com", language="ru")
        _request(user)
        assert _sent_to(NEW)[0].subject == "Подтвердите новую почту для ProofLayer"
        assert _sent_to("old@example.com")[0].subject == "Запрос на смену почты в ProofLayer"

    def test_wrong_password(self):
        user = UserFactory()
        response = _request(user, password="nope")
        assert response.status_code == 403
        assert response.data["code"] == "wrong_password"
        assert not EmailChangeToken.objects.exists()
        assert outbox.outbox == []

    def test_address_taken_by_another_account_in_any_case(self):
        UserFactory(email="taken@example.com")
        response = _request(UserFactory(), new_email="TAKEN@Example.com")
        assert response.status_code == 400
        assert response.data["code"] == "email_taken"
        assert not EmailChangeToken.objects.exists()

    def test_same_address(self):
        user = UserFactory(email="me@example.com")
        response = _request(user, new_email="ME@example.COM")
        assert response.status_code == 400
        assert response.data["code"] == "same_email"

    @pytest.mark.parametrize(
        "value",
        [
            "", "not-an-email", "a@b", "x@demo.prooflayer.cloud", "x@ｄemo.prooflayer.cloud", "a" * 250 + "@example.com",
            "x@localhost", "x@[127.0.0.1]", "фуу@example.com", "x@example.com.", "x@exa..mple.com",
        ],
    )
    def test_invalid_address(self, value):
        response = _request(UserFactory(), new_email=value)
        assert response.status_code == 400
        assert response.data["code"] == "invalid_email"

    def test_address_is_trimmed_and_domain_lowercased(self):
        response = _request(UserFactory(), new_email="  Someone@EXAMPLE.com ")
        assert response.data["pending_email"] == "Someone@example.com"

    def test_fullwidth_letters_cannot_dodge_a_taken_address(self):
        UserFactory(email="taken@example.com")
        response = _request(UserFactory(), new_email="ｔaken@ｅxample.ｃom")
        assert response.status_code == 400
        assert response.data["code"] == "email_taken"

    def test_lookalike_domain_is_kept_in_its_visible_ascii_form(self):
        user = UserFactory(email="old@example.com")
        response = _request(user, new_email="teacher@gmаil.com")
        assert response.status_code == 202
        assert response.data["pending_email"] == "teacher@xn--gmil-63d.com"
        assert len(_sent_to("teacher@xn--gmil-63d.com")) == 1
        assert "t***@xn--gmil-63d.com" in _sent_to("old@example.com")[0].body

    def test_international_domain_matches_an_account_stored_in_unicode(self):
        UserFactory(email="ivan@почта.рф")
        response = _request(UserFactory(), new_email="Ivan@ПОЧТА.РФ")
        assert response.status_code == 400
        assert response.data["code"] == "email_taken"

    def test_own_address_in_another_form_is_the_same_address(self):
        user = UserFactory(email="ivan@почта.рф")
        response = _request(user, new_email="ivan@xn--80a1acny.xn--p1ai")
        assert response.status_code == 400
        assert response.data["code"] == "same_email"

    def test_new_request_replaces_the_older_one(self):
        user = UserFactory()
        _request(user, new_email="first@example.com")
        first = _token(user)
        _request(user, new_email="second@example.com")
        first.refresh_from_db()
        assert first.cancelled_at is not None
        assert EmailChangeToken.objects.open().filter(user=user).count() == 1
        response = _confirm(first.token)
        assert response.status_code == 410
        assert response.data["code"] == "cancelled"

    def test_throttled_after_five_attempts(self):
        user = UserFactory()
        for _ in range(5):
            assert _request(user, password="wrong").status_code == 403
        assert _request(user).status_code == 429

    def test_api_key_cannot_change_the_email(self):
        user = UserFactory()
        _, raw = ApiKey.issue(user, "script")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw}")
        response = client.post(reverse("email-change"), {"new_email": NEW, "password": PASSWORD}, format="json")
        assert response.status_code == 401
        assert not EmailChangeToken.objects.exists()

    def test_cancel(self):
        user = UserFactory()
        _request(user)
        change = _token(user)
        response = _client(user).delete(reverse("email-change"))
        assert response.status_code == 200
        assert response.data["pending_email"] is None
        assert _client(user).get(reverse("me")).data["pending_email"] is None
        assert _confirm(change.token).data["code"] == "cancelled"

    def test_resend_sends_the_same_link_with_a_fresh_day(self):
        user = UserFactory()
        _request(user)
        change = _token(user)
        EmailChangeToken.objects.filter(pk=change.pk).update(expires_at=timezone.now() + timedelta(minutes=5))
        response = _client(user).post(reverse("email-change-resend"))
        assert response.status_code == 200
        assert response.data["pending_email"] == NEW
        mails = _sent_to(NEW)
        assert len(mails) == 2
        assert change.token in mails[-1].body
        change.refresh_from_db()
        assert change.expires_at > timezone.now() + timedelta(hours=23)

    def test_confirm_mail_does_not_show_the_old_address(self):
        user = UserFactory(email="old.private@example.com")
        User.objects.filter(pk=user.pk).update(username="", first_name="", last_name="")
        user.refresh_from_db()
        _request(user)
        [confirm] = _sent_to(NEW)
        assert "old.private@example.com" not in confirm.body
        assert "old.private@example.com" not in confirm.alternatives[0][0]

    def test_resend_without_a_pending_change(self):
        response = _client(UserFactory()).post(reverse("email-change-resend"))
        assert response.status_code == 404
        assert response.data["code"] == "no_pending"


@pytest.mark.django_db
class TestConfirm:
    def test_confirm_changes_the_address_and_marks_it_verified(self):
        user = UserFactory(email="old@example.com", is_verified=False)
        stale = EmailVerificationToken.objects.create(user=user)
        _request(user)
        change = _token(user)
        outbox.outbox.clear()
        response = _confirm(change.token)
        assert response.status_code == 200
        assert response.data["email"] == NEW
        user.refresh_from_db()
        assert user.email == NEW
        assert user.is_verified is True
        change.refresh_from_db()
        assert change.used_at is not None
        stale.refresh_from_db()
        assert stale.used_at is not None
        [notice] = outbox.outbox
        assert notice.to == ["old@example.com"]
        assert notice.subject == "Your ProofLayer email was changed"
        assert "n***@example.com" in notice.body

    def test_sign_in_uses_the_new_address(self):
        user = UserFactory(email="old@example.com")
        _request(user)
        _confirm(_token(user).token)
        client = APIClient()
        assert client.post(reverse("login"), {"email": NEW, "password": PASSWORD}, format="json").status_code == 200
        assert client.post(reverse("login"), {"email": "old@example.com", "password": PASSWORD}, format="json").status_code == 401

    def test_opening_the_link_again_changes_nothing_and_says_it_is_done(self):
        user = UserFactory(email="old@example.com")
        _request(user)
        token = _token(user).token
        assert _confirm(token).status_code == 200
        outbox.outbox.clear()
        again = _confirm(token)
        assert again.status_code == 200
        assert again.data["email"] == NEW
        assert outbox.outbox == []
        user.refresh_from_db()
        assert user.email == NEW

    def test_used_link_cannot_switch_the_address_back(self):
        user = UserFactory(email="old@example.com")
        _request(user)
        first = _token(user).token
        _confirm(first)
        _request(User.objects.get(pk=user.pk), new_email="third@example.com")
        _confirm(_token(user).token)
        again = _confirm(first)
        assert again.status_code == 410
        assert again.data["code"] == "used"
        user.refresh_from_db()
        assert user.email == "third@example.com"

    def test_password_change_by_any_route_kills_the_link(self):
        user = UserFactory(email="old@example.com")
        _request(user)
        change = _token(user)
        user.set_password("Changed-By-Admin-2026")
        user.save(update_fields=["password"])
        fresh = User.objects.get(pk=user.pk)
        assert _client(fresh).get(reverse("me")).data["pending_email"] is None
        assert _client(fresh).post(reverse("email-change-resend")).status_code == 404
        response = _confirm(change.token)
        assert response.status_code == 410
        assert response.data["code"] == "cancelled"
        change.refresh_from_db()
        assert change.cancelled_at is not None
        fresh.refresh_from_db()
        assert fresh.email == "old@example.com"

    def test_token_without_a_password_stamp_is_refused(self):
        user = UserFactory(email="old@example.com")
        change = EmailChangeToken.objects.create(user=user, new_email=NEW)
        assert _confirm(change.token).data["code"] == "cancelled"
        user.refresh_from_db()
        assert user.email == "old@example.com"

    def test_expired_link(self):
        user = UserFactory(email="old@example.com")
        _request(user)
        change = _token(user)
        EmailChangeToken.objects.filter(pk=change.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        response = _confirm(change.token)
        assert response.status_code == 410
        assert response.data["code"] == "expired"
        user.refresh_from_db()
        assert user.email == "old@example.com"

    def test_unknown_or_missing_token(self):
        assert _confirm("nope").status_code == 404
        assert _confirm("nope").data["code"] == "invalid"
        assert _confirm("").status_code == 400

    def test_address_taken_in_the_meantime(self):
        user = UserFactory(email="old@example.com")
        _request(user)
        change = _token(user)
        UserFactory(email="NEW@example.com")
        response = _confirm(change.token)
        assert response.status_code == 409
        assert response.data["code"] == "email_taken"
        user.refresh_from_db()
        assert user.email == "old@example.com"
        change.refresh_from_db()
        assert change.used_at is None

    def test_database_race_is_reported_as_taken(self):
        user = UserFactory(email="old@example.com")
        _request(user)
        change = _token(user)
        UserFactory(email=NEW)
        with patch("users.views._email_in_use", return_value=False):
            response = _confirm(change.token)
        assert response.status_code == 409
        assert response.data["code"] == "email_taken"
        user.refresh_from_db()
        assert user.email == "old@example.com"
        change.refresh_from_db()
        assert change.used_at is None

    def test_old_password_reset_links_stop_working(self):
        user = UserFactory(email="old@example.com")
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_token = default_token_generator.make_token(user)
        _request(user)
        _confirm(_token(user).token)
        user.refresh_from_db()
        assert not default_token_generator.check_token(user, reset_token)
        response = APIClient().post(
            reverse("password-reset-confirm"),
            {"uid": uid, "token": reset_token, "password": "Fresh-Pass-2026"},
            format="json",
        )
        assert response.status_code == 400
        user.refresh_from_db()
        assert user.check_password(PASSWORD)

    def test_password_reset_cancels_a_pending_change(self):
        user = UserFactory()
        _request(user)
        change = _token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_token = default_token_generator.make_token(user)
        reset = APIClient().post(
            reverse("password-reset-confirm"),
            {"uid": uid, "token": reset_token, "password": "Fresh-Pass-2026"},
            format="json",
        )
        assert reset.status_code == 200
        assert _confirm(change.token).data["code"] == "cancelled"


@pytest.mark.django_db
class TestPayload:
    def test_me_shows_the_pending_address_until_it_expires(self):
        user = UserFactory()
        client = _client(user)
        assert client.get(reverse("me")).data["pending_email"] is None
        _request(user)
        assert client.get(reverse("me")).data["pending_email"] == NEW
        EmailChangeToken.objects.filter(user=user).update(expires_at=timezone.now() - timedelta(seconds=1))
        assert client.get(reverse("me")).data["pending_email"] is None

    def test_me_clears_the_pending_address_after_confirm(self):
        user = UserFactory()
        _request(user)
        _confirm(_token(user).token)
        data = _client(User.objects.get(pk=user.pk)).get(reverse("me")).data
        assert data["pending_email"] is None
        assert data["email"] == NEW
        assert data["is_demo"] is False


def _confirm_in_thread(token, results):
    try:
        results[token] = _confirm(token).status_code
    finally:
        connection.close()


@pytest.mark.django_db(transaction=True)
def test_two_accounts_racing_for_one_address_in_different_case():
    first = UserFactory(email="first@example.com")
    second = UserFactory(email="second@example.com")
    _request(first, new_email="Shared@example.com")
    _request(second, new_email="shared@example.com")
    tokens = [_token(first).token, _token(second).token]
    real_check = user_views._email_in_use

    def slow_check(email, user):
        taken = real_check(email, user)
        time.sleep(0.6)
        return taken

    results = {}
    with patch("users.views._email_in_use", side_effect=slow_check):
        threads = [threading.Thread(target=_confirm_in_thread, args=(token, results)) for token in tokens]
        threads[0].start()
        time.sleep(0.2)
        threads[1].start()
        for thread in threads:
            thread.join()
    assert sorted(results.values()) == [200, 409]
    assert User.objects.filter(email__iexact="shared@example.com").count() == 1
