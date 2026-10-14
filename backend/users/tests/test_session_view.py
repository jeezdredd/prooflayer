import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestSessionView:
    def test_reports_the_cookie_owner_without_rotating(self):
        user = UserFactory()
        client = APIClient()
        raw = str(RefreshToken.for_user(user))
        client.cookies[settings.REFRESH_COOKIE_NAME] = raw
        response = client.get(reverse("session"))
        assert response.status_code == 200
        assert response.data["user_id"] == user.id
        assert settings.REFRESH_COOKIE_NAME not in response.cookies

    def test_no_or_bad_cookie_means_no_session(self):
        client = APIClient()
        assert client.get(reverse("session")).data["user_id"] is None
        client.cookies[settings.REFRESH_COOKIE_NAME] = "garbage"
        assert client.get(reverse("session")).data["user_id"] is None
