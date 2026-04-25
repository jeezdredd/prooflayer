import uuid

from django.db import models


class ProvenanceResult(models.Model):
    class SourceType(models.TextChoices):
        PHASH_MATCH = "phash_match", "pHash Match"
        TINEYE = "tineye", "TinEye"
        GOOGLE_VISION = "google_vision", "Google Vision"
        C2PA = "c2pa", "C2PA"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        "content.Submission",
        on_delete=models.CASCADE,
        related_name="provenance_results",
    )
    source_type = models.CharField(max_length=30, choices=SourceType.choices, db_index=True)
    source_url = models.URLField(blank=True, max_length=2000)
    title = models.CharField(max_length=500, blank=True)
    similarity_score = models.FloatField(null=True, blank=True)
    raw_data = models.JSONField(default=dict)
    found_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "provenance_results"
        ordering = ["-found_at"]

    def __str__(self):
        return f"{self.source_type} — {self.submission_id}"
