from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0003_submission_dhash_submission_phash"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="status_message",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
