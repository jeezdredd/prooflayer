import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.crypto import constant_time_compare


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        user = self.by_email(email)
        if user is None:
            raise self.model.DoesNotExist
        return user

    def by_email(self, email):
        if not email:
            return None
        exact = self.filter(email=email).first()
        if exact is not None:
            return exact
        matches = list(self.filter(email__iexact=email)[:2])
        return matches[0] if len(matches) == 1 else None

    def create_superuser(self, email, username, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_verified", True)
        return self.create_user(email, username, password, **extra)


class User(AbstractUser):
    class Language(models.TextChoices):
        EN = "en", "English"
        RU = "ru", "Русский"

    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    bio = models.TextField(max_length=500, blank=True)
    is_verified = models.BooleanField(default=False)
    allow_training = models.BooleanField(default=False)
    training_consent_at = models.DateTimeField(null=True, blank=True)
    is_adult = models.BooleanField(default=False)
    age_confirmed_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=20, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.EN)
    email_updates = models.BooleanField(default=True)

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


EMAIL_CHANGE_HOURS = 24


def email_change_expiry():
    return timezone.now() + timedelta(hours=EMAIL_CHANGE_HOURS)


class EmailChangeQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(used_at__isnull=True, cancelled_at__isnull=True, expires_at__gt=timezone.now())

    def open(self):
        return self.filter(used_at__isnull=True, cancelled_at__isnull=True)


class EmailChangeToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_change_tokens")
    new_email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, default=_gen_token, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=email_change_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    password_stamp = models.CharField(max_length=128, blank=True)

    objects = EmailChangeQuerySet.as_manager()

    class Meta:
        db_table = "email_change_tokens"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(used_at__isnull=True, cancelled_at__isnull=True),
                name="one_open_email_change_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.new_email}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def password_unchanged(self) -> bool:
        return bool(self.password_stamp) and constant_time_compare(self.password_stamp, self.user.get_session_auth_hash())

    @classmethod
    def start(cls, user, new_email: str) -> "EmailChangeToken":
        cls.cancel_open(user)
        return cls.objects.create(user=user, new_email=new_email, password_stamp=user.get_session_auth_hash())

    @classmethod
    def cancel_open(cls, user) -> int:
        return cls.objects.open().filter(user=user).update(cancelled_at=timezone.now())

    @classmethod
    def pending_for(cls, user) -> "EmailChangeToken | None":
        change = cls.objects.pending().filter(user=user).first()
        if change is None:
            return None
        change.user = user
        return change if change.password_unchanged() else None


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


API_KEY_PREFIX = "pl_"
API_KEY_VISIBLE_CHARS = 11


def _hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ApiKey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=80)
    prefix = models.CharField(max_length=16, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    webhook_url = models.URLField(max_length=500, blank=True)
    webhook_secret = models.CharField(max_length=64, blank=True)
    last_webhook_at = models.DateTimeField(null=True, blank=True)
    last_webhook_status = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "api_keys"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.prefix}... ({self.user.email})"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @classmethod
    def issue(cls, user, name: str, webhook_url: str = "") -> tuple["ApiKey", str]:
        raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
        key = cls.objects.create(
            user=user,
            name=name,
            prefix=raw[:API_KEY_VISIBLE_CHARS],
            key_hash=_hash_api_key(raw),
            webhook_url=webhook_url,
            webhook_secret=cls.new_webhook_secret() if webhook_url else "",
        )
        return key, raw

    @staticmethod
    def new_webhook_secret() -> str:
        return "whsec_" + secrets.token_hex(24)

    @classmethod
    def lookup(cls, raw: str) -> "ApiKey | None":
        if not raw or not raw.startswith(API_KEY_PREFIX):
            return None
        return cls.objects.select_related("user").filter(key_hash=_hash_api_key(raw)).first()


class ProductUpdate(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"

    title_en = models.CharField(max_length=160)
    title_ru = models.CharField(max_length=160)
    summary_en = models.CharField(max_length=300, blank=True, help_text="Inbox preview line")
    summary_ru = models.CharField(max_length=300, blank=True, help_text="Строка превью во входящих")
    body_en = models.TextField(help_text="Paragraphs separated by a blank line. Lines starting with '- ' become a list.")
    body_ru = models.TextField(help_text="Абзацы через пустую строку. Строки с '- ' становятся списком.")
    cta_label_en = models.CharField(max_length=60, blank=True)
    cta_label_ru = models.CharField(max_length=60, blank=True)
    cta_url = models.URLField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipients = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "product_updates"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title_en

    def localized(self, lang: str) -> dict:
        ru = lang == User.Language.RU
        return {
            "title": self.title_ru if ru else self.title_en,
            "summary": (self.summary_ru if ru else self.summary_en) or "",
            "body": self.body_ru if ru else self.body_en,
            "cta_label": (self.cta_label_ru if ru else self.cta_label_en) or "",
        }


class ProductUpdateDelivery(models.Model):
    update = models.ForeignKey(ProductUpdate, on_delete=models.CASCADE, related_name="deliveries")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="update_deliveries")
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_update_deliveries"
        constraints = [models.UniqueConstraint(fields=["update", "user"], name="uniq_update_delivery")]
