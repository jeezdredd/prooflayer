from django.db import migrations


def drop(apps, schema_editor):
    apps.get_model("api", "ChangelogEntry").objects.filter(slug="front-page-plain-words").delete()


class Migration(migrations.Migration):
    dependencies = [("api", "0010_roadmap_passport_is_writing_replay")]
    operations = [migrations.RunPython(drop, migrations.RunPython.noop)]
