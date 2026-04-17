from django.core.management.base import BaseCommand

from analyzers.models import AnalyzerConfig

ANALYZERS = [
    {
        "name": "metadata",
        "analyzer_class": "analyzers.implementations.metadata_analyzer.MetadataAnalyzer",
        "version": "1.0.0",
        "weight": 1.0,
        "queue": "default",
        "timeout": 60,
    },
]


class Command(BaseCommand):
    help = "Seed analyzer configurations"

    def handle(self, *args, **options):
        for analyzer_data in ANALYZERS:
            obj, created = AnalyzerConfig.objects.update_or_create(
                name=analyzer_data["name"],
                defaults=analyzer_data,
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status}: {obj.name} v{obj.version}")
