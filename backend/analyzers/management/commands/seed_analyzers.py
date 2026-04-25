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
    {
        "name": "ela",
        "analyzer_class": "analyzers.implementations.ela_analyzer.ELAAnalyzer",
        "version": "1.0.0",
        "weight": 1.5,
        "queue": "default",
        "timeout": 60,
    },
    {
        "name": "ai_detector",
        "analyzer_class": "analyzers.implementations.clip_detector.AIImageDetector",
        "version": "1.0.0",
        "weight": 2.0,
        "queue": "ml",
        "timeout": 120,
    },
    {
        "name": "video_frame",
        "analyzer_class": "analyzers.implementations.video_analyzer.VideoFrameAnalyzer",
        "version": "1.0.0",
        "weight": 2.0,
        "queue": "ml",
        "timeout": 300,
    },
    {
        "name": "llm_text",
        "analyzer_class": "analyzers.implementations.llm_analyzer.LLMTextAnalyzer",
        "version": "1.0.0",
        "weight": 2.5,
        "queue": "ml",
        "timeout": 180,
    },
    {
        "name": "audio_spectrogram",
        "analyzer_class": "analyzers.implementations.audio_analyzer.AudioSpectrogramAnalyzer",
        "version": "1.0.0",
        "weight": 2.0,
        "queue": "ml",
        "timeout": 120,
    },
]


class Command(BaseCommand):
    help = "Seed analyzer configurations"

    def handle(self, *args, **options):
        active_names = {a["name"] for a in ANALYZERS}
        for analyzer_data in ANALYZERS:
            obj, created = AnalyzerConfig.objects.update_or_create(
                name=analyzer_data["name"],
                defaults=analyzer_data,
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status}: {obj.name} v{obj.version}")

        stale = AnalyzerConfig.objects.exclude(name__in=active_names).filter(is_active=True)
        for config in stale:
            config.is_active = False
            config.save(update_fields=["is_active"])
            self.stdout.write(f"Deactivated: {config.name}")
