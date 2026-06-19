import uuid

from django.conf import settings
from django.db import models


class AnalyzerConfig(models.Model):
    name = models.CharField(max_length=100, unique=True)
    analyzer_class = models.CharField(max_length=255)
    version = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    weight = models.FloatField(default=1.0)
    queue = models.CharField(max_length=50, default="default")
    timeout = models.PositiveIntegerField(default=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analyzer_configs"

    def __str__(self):
        return f"{self.name} v{self.version}"


class AnalysisResult(models.Model):
    class Verdict(models.TextChoices):
        AUTHENTIC = "authentic"
        SUSPICIOUS = "suspicious"
        FAKE = "fake"
        INCONCLUSIVE = "inconclusive"
        ERROR = "error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        "content.Submission",
        on_delete=models.CASCADE,
        related_name="analysis_results",
    )
    analyzer = models.ForeignKey(
        AnalyzerConfig,
        on_delete=models.PROTECT,
        related_name="results",
    )
    confidence = models.FloatField(default=0.0)
    verdict = models.CharField(max_length=20, choices=Verdict.choices)
    evidence = models.JSONField(default=dict)
    execution_time = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analysis_results"
        unique_together = [("submission", "analyzer")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.analyzer.name}: {self.verdict} ({self.confidence:.2f})"


class RetrainRun(models.Model):
    class Status(models.TextChoices):
        STARTED = "started"
        SUCCESS = "success"
        SKIPPED = "skipped"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    media_type = models.CharField(max_length=20, default="image")
    samples_used = models.PositiveIntegerField(default=0)
    epochs = models.PositiveIntegerField(default=3)
    hf_revision = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.STARTED)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retrain_runs",
    )

    class Meta:
        db_table = "retrain_runs"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.media_type} {self.status} {self.started_at:%Y-%m-%d}"
