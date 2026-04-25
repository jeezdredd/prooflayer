import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("content", "0003_submission_dhash_submission_phash"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProvenanceResult",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "submission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="provenance_results",
                        to="content.submission",
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("phash_match", "pHash Match"),
                            ("tineye", "TinEye"),
                            ("google_vision", "Google Vision"),
                            ("c2pa", "C2PA"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("source_url", models.URLField(blank=True, max_length=2000)),
                ("title", models.CharField(blank=True, max_length=500)),
                ("similarity_score", models.FloatField(blank=True, null=True)),
                ("raw_data", models.JSONField(default=dict)),
                ("found_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "provenance_results", "ordering": ["-found_at"]},
        ),
    ]
