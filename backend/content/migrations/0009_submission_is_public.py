from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0008_knownfakehash_dhash_knownfakehash_pdq_hash_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="is_public",
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
