from django.db import migrations


def promote(apps, schema_editor):
    RoadmapItem = apps.get_model("api", "RoadmapItem")
    RoadmapItem.objects.filter(title="Faster vision judge on our GPU", status="building").update(status="beta")


class Migration(migrations.Migration):
    dependencies = [("api", "0007_roadmap_passages_beta")]
    operations = [migrations.RunPython(promote, migrations.RunPython.noop)]
