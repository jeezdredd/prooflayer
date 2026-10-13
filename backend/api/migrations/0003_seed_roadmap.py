from django.db import migrations

ITEMS = [
    (
        10,
        "building",
        "Text detector v2",
        "A classifier trained on 2026 generators and on humanized text in Russian, English and French. "
        "It gets a vote only after it beats the current bench on a frozen test set without new false accusations.",
    ),
    (
        20,
        "building",
        "Faster vision judge on our GPU",
        "The vision model moves to our own GPU: shorter waits on image checks and a newer model that names "
        "defects more carefully.",
    ),
    (
        30,
        "exploring",
        "Highlighted passages in essays",
        "Sentence-level marks that show which parts of a text drove the verdict, so a teacher can go through "
        "specific lines with the student.",
    ),
    (
        40,
        "exploring",
        "More languages for text checks",
        "Russian, English and French today. Each new language is added once it has its own calibration set.",
    ),
]


def seed(apps, schema_editor):
    RoadmapItem = apps.get_model("api", "RoadmapItem")
    if RoadmapItem.objects.exists():
        return
    for position, status, title, body in ITEMS:
        RoadmapItem.objects.create(position=position, status=status, title=title, body=body)


def unseed(apps, schema_editor):
    RoadmapItem = apps.get_model("api", "RoadmapItem")
    RoadmapItem.objects.filter(title__in=[title for _, _, title, _ in ITEMS]).delete()


class Migration(migrations.Migration):
    dependencies = [("api", "0002_roadmap_item")]

    operations = [migrations.RunPython(seed, unseed)]
