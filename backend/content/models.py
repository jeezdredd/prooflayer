import uuid

from django.conf import settings
from django.db import models


class Submission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="submissions/%Y/%m/%d/")
    thumbnail = models.ImageField(upload_to="thumbnails/%Y/%m/%d/", blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    sha256_hash = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    status_message = models.CharField(max_length=100, blank=True)
    final_score = models.FloatField(null=True, blank=True)
    final_verdict = models.CharField(max_length=30, blank=True)
    is_known_fake = models.BooleanField(default=False)
    phash = models.BigIntegerField(null=True, blank=True, db_index=True)
    dhash = models.BigIntegerField(null=True, blank=True, db_index=True)
    approved_for_training = models.BooleanField(default=False, db_index=True)
    verified_label = models.CharField(
        max_length=10,
        blank=True,
        choices=[("real", "Real"), ("fake", "Fake")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "submissions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.status})"


class KnownFakeHash(models.Model):
    sha256_hash = models.CharField(max_length=64, unique=True, db_index=True)
    source = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "known_fake_hashes"

    def __str__(self):
        return f"{self.sha256_hash[:16]}... ({self.source})"


class VerdictOverride(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="verdict_overrides",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="verdict_overrides",
    )
    previous_verdict = models.CharField(max_length=30, blank=True)
    new_verdict = models.CharField(max_length=30)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "verdict_overrides"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.submission_id} {self.previous_verdict}→{self.new_verdict}"
