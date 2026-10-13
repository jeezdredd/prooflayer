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


class RoadmapItem(models.Model):
    class Status(models.TextChoices):
        EXPLORING = "exploring", "Exploring"
        BUILDING = "building", "Building"
        BETA = "beta", "In beta"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=120)
    body = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.EXPLORING)
    eta = models.CharField(max_length=40, blank=True, default="")
    position = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at"]

    def __str__(self):
        return self.title
