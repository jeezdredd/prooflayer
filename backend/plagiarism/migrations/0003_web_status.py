from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plagiarism', '0002_repository_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='plagiarismreport',
            name='web_status',
            field=models.CharField(blank=True, choices=[('ok', 'Searched'), ('failed', 'Search did not respond'), ('off', 'Search is off'), ('short', 'Too short to search')], max_length=8),
        ),
        migrations.AddField(
            model_name='plagiarismreport',
            name='web_engines',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
