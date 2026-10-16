import re

from django.db import migrations

RUSSIAN = re.compile(r"Трибунал[а-яё]*")


def brand(text: str) -> str:
    return RUSSIAN.sub("Tribunal", text.replace("текущим Трибуналом", "текущей версией Tribunal"))


def rename(apps, schema_editor):
    for model in ("RoadmapItem", "ChangelogEntry"):
        for row in apps.get_model("api", model).objects.all():
            changed = [f for f in ("title_ru", "body_ru") if brand(getattr(row, f)) != getattr(row, f)]
            for field in changed:
                setattr(row, field, brand(getattr(row, field)))
            if changed:
                row.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("api", "0012_roadmap_humanizer_proof_shipped")]
    operations = [migrations.RunPython(rename, migrations.RunPython.noop)]
