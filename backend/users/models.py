import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_verified", True)
        return self.create_user(email, username, password, **extra)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    bio = models.TextField(max_length=500, blank=True)
    is_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]


def _gen_token() -> str:
    return secrets.token_urlsafe(32)


def _default_expiry():
    return timezone.now() + timedelta(hours=48)


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_tokens")
    token = models.CharField(max_length=64, unique=True, default=_gen_token, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_expiry)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "email_verification_tokens"
        ordering = ["-created_at"]

    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() < self.expires_at

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])


class EmailLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    to_email = models.CharField(max_length=254)
    kind = models.CharField(max_length=20, default="other")
    subject = models.CharField(max_length=255, blank=True)
    backend = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    error = models.TextField(blank=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
    )

    class Meta:
        db_table = "email_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} {self.status} {self.to_email}"
