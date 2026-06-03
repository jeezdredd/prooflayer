import uuid

from django.conf import settings
from django.db import models


class Feedback(models.Model):
    class Category(models.TextChoices):
        ACCURACY = "accuracy", "Accuracy"
        UX = "ux", "UX / Design"
        PERFORMANCE = "performance", "Performance"
        FEATURE_REQUEST = "feature_request", "Feature Request"
        BUG = "bug", "Bug Report"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.OTHER)
    message = models.TextField()
    contact_email = models.EmailField(blank=True, default="")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="feedback",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_category_display()} | {str(self.id)[:8]}"
