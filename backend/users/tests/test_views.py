import pytest
from django.urls import reverse
from rest_framework.test import APIClient

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
        }
        response = self.client.post(self.url, data)
        assert response.status_code == 201
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]
        assert response.data["user"]["email"] == "new@example.com"

    def test_register_password_mismatch(self):
        data = {
            "email": "new@example.com",
            "username": "newuser",
            "password": "StrongPass123!",
            "password_confirm": "DifferentPass123!",
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
        assert "refresh" in response.data

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
