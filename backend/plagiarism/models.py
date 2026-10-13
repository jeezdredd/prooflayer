import uuid

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from pgvector.django import HnswIndex, VectorField

EMBED_DIM = 384


class TextFingerprint(models.Model):
    submission = models.OneToOneField("content.Submission", on_delete=models.CASCADE, primary_key=True, related_name="text_fingerprint")
    language = models.CharField(max_length=8, blank=True)
    text = models.TextField()
    fingerprints = ArrayField(models.BigIntegerField(), default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "plagiarism_fingerprints"
        indexes = [GinIndex(fields=["fingerprints"], name="plag_fp_gin")]


class SentenceVector(models.Model):
    submission = models.ForeignKey("content.Submission", on_delete=models.CASCADE, related_name="sentence_vectors")
    position = models.PositiveIntegerField()
    start = models.PositiveIntegerField()
    end = models.PositiveIntegerField()
    language = models.CharField(max_length=8, blank=True)
    embedding = VectorField(dimensions=EMBED_DIM)

    class Meta:
        db_table = "plagiarism_sentence_vectors"
        ordering = ["submission_id", "position"]
        indexes = [
            HnswIndex(
                name="plag_sentence_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]


class PlagiarismReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.OneToOneField("content.Submission", on_delete=models.CASCADE, related_name="plagiarism_report")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    originality = models.FloatField(null=True, blank=True)
    matched_chars = models.PositiveIntegerField(default=0)
    total_chars = models.PositiveIntegerField(default=0)
    matches = models.JSONField(default=list, blank=True)
    web_searched = models.BooleanField(default=False)
    web_queries = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "plagiarism_reports"
