from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0019_submission_uploaded_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='verdictobjection',
            name='original_verdict',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
    ]
