from django.db import migrations


def promote(apps, schema_editor):
    RoadmapItem = apps.get_model("api", "RoadmapItem")
    RoadmapItem.objects.filter(title="Highlighted passages in essays", status="exploring").update(status="beta")


class Migration(migrations.Migration):
    dependencies = [("api", "0006_roadmap_ru_text")]
    operations = [migrations.RunPython(promote, migrations.RunPython.noop)]
