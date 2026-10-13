import importlib
from datetime import timedelta

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from common.age import can_view_sensitive
from content.tests.factories import SubmissionFactory
from users.models import User
from users.serializers import ACCEPT_TERMS_MESSAGE

from .factories import UserFactory

mark_staff_adult = importlib.import_module("users.migrations.0006_age_and_terms").mark_staff_adult

PASSWORD = "StrongPass123!"


def _payload(**extra):
    data = {
        "email": "kid@example.com",
        "username": "kid",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
        "accept_terms": True,
    }
    data.update(extra)
    return data


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestRegisterTerms:
    def test_missing_accept_terms_is_rejected(self):
        data = _payload()
        data.pop("accept_terms")
        response = _client().post(reverse("register"), data, format="json")
        assert response.status_code == 400
        assert response.data["accept_terms"] == [ACCEPT_TERMS_MESSAGE]
        assert not User.objects.filter(email="kid@example.com").exists()

    def test_false_accept_terms_is_rejected(self):
        response = _client().post(reverse("register"), _payload(accept_terms=False), format="json")
        assert response.status_code == 400
        assert response.data["accept_terms"] == [ACCEPT_TERMS_MESSAGE]

    def test_false_accept_terms_in_form_data_is_rejected(self):
        response = _client().post(reverse("register"), _payload(accept_terms=False))
        assert response.status_code == 400
        assert response.data["accept_terms"] == [ACCEPT_TERMS_MESSAGE]

    def test_register_without_age_is_minor_with_current_terms(self):
        response = _client().post(reverse("register"), _payload(), format="json")
        assert response.status_code == 201
        user = User.objects.get(email="kid@example.com")
        assert user.is_adult is False
        assert user.age_confirmed_at is None
        assert user.terms_version == settings.TERMS_VERSION
        assert user.terms_accepted_at is not None
        body = response.data["user"]
        assert body["is_adult"] is False
        assert body["terms_version"] == settings.TERMS_VERSION
        assert body["needs_terms"] is False
        assert "accept_terms" not in body

    def test_register_as_adult_stamps_age_confirmation(self):
        response = _client().post(reverse("register"), _payload(is_adult=True), format="json")
        assert response.status_code == 201
        user = User.objects.get(email="kid@example.com")
        assert user.is_adult is True
        assert user.age_confirmed_at is not None
        assert response.data["user"]["is_adult"] is True


@pytest.mark.django_db
class TestMeAge:
    def test_needs_terms_for_user_without_terms(self):
        user = UserFactory()
        response = _client(user).get(reverse("me"))
        assert response.status_code == 200
        assert response.data["terms_version"] == ""
        assert response.data["needs_terms"] is True
        assert response.data["is_adult"] is False

    def test_needs_terms_for_outdated_version(self):
        user = UserFactory(terms_version="2020-01-01", terms_accepted_at=timezone.now())
        response = _client(user).get(reverse("me"))
        assert response.data["needs_terms"] is True

    def test_patch_is_adult_true_stamps_confirmation(self):
        user = UserFactory()
        response = _client(user).patch(reverse("me"), {"is_adult": True}, format="json")
        assert response.status_code == 200
        assert response.data["is_adult"] is True
        user.refresh_from_db()
        assert user.is_adult is True
        assert user.age_confirmed_at is not None

    def test_patch_is_adult_true_again_keeps_original_stamp(self):
        stamped = timezone.now() - timedelta(days=10)
        user = UserFactory(is_adult=True, age_confirmed_at=stamped)
        _client(user).patch(reverse("me"), {"is_adult": True}, format="json")
        user.refresh_from_db()
        assert user.age_confirmed_at == stamped

    def test_patch_is_adult_false_keeps_record_and_unpublishes(self):
        stamped = timezone.now()
        user = UserFactory(is_adult=True, age_confirmed_at=stamped)
        public = SubmissionFactory(user=user, is_public=True, status="completed")
        response = _client(user).patch(reverse("me"), {"is_adult": False}, format="json")
        assert response.status_code == 200
        user.refresh_from_db()
        public.refresh_from_db()
        assert user.is_adult is False
        assert user.age_confirmed_at == stamped
        assert public.is_public is False

    def test_patch_other_field_leaves_age_alone(self):
        stamped = timezone.now() - timedelta(days=3)
        user = UserFactory(is_adult=True, age_confirmed_at=stamped)
        _client(user).patch(reverse("me"), {"bio": "hi"}, format="json")
        user.refresh_from_db()
        assert user.is_adult is True
        assert user.age_confirmed_at == stamped

    def test_terms_version_is_read_only(self):
        user = UserFactory()
        response = _client(user).patch(reverse("me"), {"terms_version": settings.TERMS_VERSION}, format="json")
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.terms_version == ""
        assert response.data["needs_terms"] is True


@pytest.mark.django_db
class TestAcceptTerms:
    def test_requires_auth(self):
        response = _client().post(reverse("accept-terms"), {"version": settings.TERMS_VERSION}, format="json")
        assert response.status_code == 401

    def test_accepts_current_version(self):
        user = UserFactory()
        response = _client(user).post(reverse("accept-terms"), {"version": settings.TERMS_VERSION}, format="json")
        assert response.status_code == 200
        assert response.data["terms_version"] == settings.TERMS_VERSION
        assert response.data["needs_terms"] is False
        assert response.data["email"] == user.email
        user.refresh_from_db()
        assert user.terms_version == settings.TERMS_VERSION
        assert user.terms_accepted_at is not None
        assert user.is_adult is False

    def test_rejects_wrong_version(self):
        user = UserFactory(terms_version="2020-01-01")
        response = _client(user).post(reverse("accept-terms"), {"version": "2020-01-01"}, format="json")
        assert response.status_code == 400
        assert "version" in response.data
        user.refresh_from_db()
        assert user.terms_version == "2020-01-01"
        assert user.terms_accepted_at is None

    def test_rejects_missing_version(self):
        user = UserFactory()
        response = _client(user).post(reverse("accept-terms"), {}, format="json")
        assert response.status_code == 400
        assert "version" in response.data

    def test_sets_is_adult_when_given(self):
        user = UserFactory()
        response = _client(user).post(
            reverse("accept-terms"), {"version": settings.TERMS_VERSION, "is_adult": True}, format="json",
        )
        assert response.status_code == 200
        assert response.data["is_adult"] is True
        user.refresh_from_db()
        assert user.is_adult is True
        assert user.age_confirmed_at is not None

    def test_clears_is_adult_when_false_and_unpublishes(self):
        stamped = timezone.now()
        user = UserFactory(is_adult=True, age_confirmed_at=stamped)
        public = SubmissionFactory(user=user, is_public=True, status="completed")
        _client(user).post(
            reverse("accept-terms"), {"version": settings.TERMS_VERSION, "is_adult": False}, format="json",
        )
        user.refresh_from_db()
        public.refresh_from_db()
        assert user.is_adult is False
        assert user.age_confirmed_at == stamped
        assert public.is_public is False

    def test_omitted_is_adult_keeps_existing_age(self):
        stamped = timezone.now() - timedelta(days=5)
        user = UserFactory(is_adult=True, age_confirmed_at=stamped)
        _client(user).post(reverse("accept-terms"), {"version": settings.TERMS_VERSION})
        user.refresh_from_db()
        assert user.is_adult is True
        assert user.age_confirmed_at == stamped
        assert user.terms_version == settings.TERMS_VERSION


@pytest.mark.django_db
class TestCanViewSensitive:
    def test_anonymous_cannot(self):
        assert can_view_sensitive(AnonymousUser()) is False

    def test_none_cannot(self):
        assert can_view_sensitive(None) is False

    def test_minor_cannot(self):
        assert can_view_sensitive(UserFactory()) is False

    def test_adult_can(self):
        assert can_view_sensitive(UserFactory(is_adult=True)) is True

    def test_staff_can(self):
        assert can_view_sensitive(UserFactory(is_staff=True)) is True

    def test_superuser_can(self):
        assert can_view_sensitive(UserFactory(is_superuser=True)) is True


@pytest.mark.django_db
class TestStaffAdultMigration:
    def test_only_staff_and_superusers_become_adult(self):
        staff = UserFactory(is_staff=True)
        superuser = UserFactory(is_superuser=True)
        regular = UserFactory()
        mark_staff_adult(apps, None)
        for user in (staff, superuser, regular):
            user.refresh_from_db()
        assert staff.is_adult is True
        assert superuser.is_adult is True
        assert regular.is_adult is False
        assert staff.terms_version == ""
        assert regular.terms_version == ""
