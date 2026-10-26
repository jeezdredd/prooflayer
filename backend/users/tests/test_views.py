from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import User

from .factories import UserFactory


@pytest.mark.django_db
class TestRegisterView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("register")

    def test_register_success(self):
        data = {
            "email": "new@example.com",
            "username": "newuser",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "accept_terms": True,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == 201
        assert "access" in response.data
        assert "user" in response.data
        assert response.data["user"]["email"] == "new@example.com"

    def test_register_training_consent_on_by_default(self):
        data = {
            "email": "consent@example.com",
            "username": "consentuser",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "accept_terms": True,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == 201
        user = User.objects.get(email="consent@example.com")
        assert user.allow_training is True
        assert user.training_consent_at is not None

    def test_register_can_decline_training(self):
        data = {
            "email": "noconsent@example.com",
            "username": "noconsentuser",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "accept_terms": True,
            "allow_training": False,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == 201
        user = User.objects.get(email="noconsent@example.com")
        assert user.allow_training is False
        assert user.training_consent_at is None

    def test_register_password_mismatch(self):
        data = {
            "email": "new@example.com",
            "username": "newuser",
            "password": "StrongPass123!",
            "password_confirm": "DifferentPass123!",
            "accept_terms": True,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == 400

    def test_register_duplicate_email(self):
        UserFactory(email="dup@example.com")
        data = {
            "email": "dup@example.com",
            "username": "another",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "accept_terms": True,
        }
        response = self.client.post(self.url, data)
        assert response.status_code == 400


@pytest.mark.django_db
class TestLoginView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("login")

    def test_login_success(self):
        user = UserFactory(email="login@example.com")
        data = {"email": "login@example.com", "password": "testpass123"}
        response = self.client.post(self.url, data)
        assert response.status_code == 200
        assert "access" in response.data

    def test_login_wrong_password(self):
        UserFactory(email="login@example.com")
        data = {"email": "login@example.com", "password": "wrongpass"}
        response = self.client.post(self.url, data)
        assert response.status_code == 401


@pytest.mark.django_db
class TestMeView:
    def setup_method(self):
        self.client = APIClient()
        self.url = reverse("me")

    def test_me_authenticated(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["email"] == user.email

    def test_me_unauthenticated(self):
        response = self.client.get(self.url)
        assert response.status_code == 401

    def test_me_update(self):
        user = UserFactory()
        self.client.force_authenticate(user=user)
        response = self.client.patch(self.url, {"bio": "Hello"})
        assert response.status_code == 200
        assert response.data["bio"] == "Hello"


def _signup(email):
    return {
        "email": email,
        "username": email.split("@")[0][:20] or "user",
        "password": "StrongPass123!",
        "password_confirm": "StrongPass123!",
        "accept_terms": True,
    }


@pytest.mark.django_db
class TestEmailCase:
    def setup_method(self):
        self.client = APIClient()

    def test_same_address_in_other_letters_cannot_register_twice(self):
        UserFactory(email="teacher@school.example")
        response = self.client.post(reverse("register"), _signup("Teacher@School.Example"))
        assert response.status_code == 400
        assert "email" in response.data

    def test_look_alike_domain_is_stored_in_ascii(self):
        response = self.client.post(reverse("register"), _signup("pupil@ｅxample.com"))
        assert response.status_code == 201
        assert User.objects.filter(email="pupil@example.com").exists()

    def test_demo_address_cannot_register(self):
        response = self.client.post(reverse("register"), _signup("visitor@demo.prooflayer.cloud"))
        assert response.status_code == 400

    def test_login_ignores_letter_case(self):
        UserFactory(email="login@example.com")
        response = self.client.post(reverse("login"), {"email": "Login@Example.com", "password": "testpass123"})
        assert response.status_code == 200

    def test_old_case_twins_keep_exact_login_only(self):
        UserFactory(email="twin@example.com")
        UserFactory(email="Twin@example.com")
        exact = self.client.post(reverse("login"), {"email": "Twin@example.com", "password": "testpass123"})
        unclear = self.client.post(reverse("login"), {"email": "TWIN@example.com", "password": "testpass123"})
        assert exact.status_code == 200
        assert unclear.status_code == 401

    def test_password_reset_finds_the_account_in_other_letters(self):
        user = UserFactory(email="reset@example.com")
        with patch("users.views.send_password_reset_email.delay") as delay:
            self.client.post(reverse("password-reset"), {"email": "RESET@example.com"}, format="json")
        delay.assert_called_once_with(user.id)
