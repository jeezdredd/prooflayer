from pgvector.django import VectorExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0006_verdictoverride"),
    ]

    operations = [
        VectorExtension(),
    ]
