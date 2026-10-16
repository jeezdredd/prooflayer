from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0017_submission_is_sensitive'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='tribunal_revision',
            field=models.CharField(blank=True, max_length=16),
        ),
    ]
