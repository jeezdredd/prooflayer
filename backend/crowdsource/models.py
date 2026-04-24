import uuid

from django.conf import settings
from django.db import models


class Vote(models.Model):
    class Value(models.TextChoices):
        REAL = "real"
        FAKE = "fake"
        UNCERTAIN = "uncertain"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    submission = models.ForeignKey(
        "content.Submission",
        on_delete=models.CASCADE,
        related_name="votes",
    )
    value = models.CharField(max_length=20, choices=Value.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "votes"
        unique_together = [("user", "submission")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} -> {self.submission_id}: {self.value}"
