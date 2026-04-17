import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            username="admin",
            password="adminpass123",
        )
        assert user.is_staff
        assert user.is_superuser

    def test_email_required(self):
        with pytest.raises(ValueError, match="Email is required"):
            User.objects.create_user(email="", username="test", password="pass123")

    def test_email_unique(self):
        User.objects.create_user(email="dup@example.com", username="user1", password="pass123")
        with pytest.raises(Exception):
            User.objects.create_user(email="dup@example.com", username="user2", password="pass123")
