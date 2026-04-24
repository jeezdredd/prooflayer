import uuid

from django.conf import settings
from django.db import models


class Report(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        REVIEWED = "reviewed"
        RESOLVED = "resolved"
        DISMISSED = "dismissed"

    class Reason(models.TextChoices):
        FAKE_CONTENT = "fake_content"
        MISLEADING = "misleading"
        COPYRIGHT = "copyright"
        SPAM = "spam"
        OTHER = "other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_filed",
    )
    submission = models.ForeignKey(
        "content.Submission",
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reason = models.CharField(max_length=30, choices=Reason.choices)
    description = models.TextField(max_length=1000, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reports"
        unique_together = [("reporter", "submission")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report {self.id} ({self.reason}) - {self.status}"
