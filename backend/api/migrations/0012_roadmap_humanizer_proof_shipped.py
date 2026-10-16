from django.db import migrations

TITLE = "Humanizer-proof text check"


def hide(apps, schema_editor):
    apps.get_model("api", "RoadmapItem").objects.filter(title=TITLE).update(is_published=False)


def show(apps, schema_editor):
    apps.get_model("api", "RoadmapItem").objects.filter(title=TITLE).update(is_published=True)


class Migration(migrations.Migration):
    dependencies = [("api", "0011_drop_front_page_changelog_entry")]
    operations = [migrations.RunPython(hide, show)]
