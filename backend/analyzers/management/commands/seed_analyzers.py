import os
import subprocess

from django.core.management.base import BaseCommand

from analyzers.models import AnalyzerConfig

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


_FALLBACK_VERSIONS = {
    "analyzers.implementations.metadata_analyzer": "1.4.0",
    "analyzers.implementations.ela_analyzer": "1.4.0",
    "analyzers.implementations.siglip_detector": "1.1.0",
    "analyzers.implementations.npr_detector": "1.1.0",
    "analyzers.implementations.community_forensics": "1.3.0",
    "analyzers.implementations.video_analyzer": "1.2.0",
    "analyzers.implementations.llm_analyzer": "1.1.0",
    "analyzers.implementations.audio_analyzer": "1.2.0",
    "analyzers.implementations.llm_image_analyzer": "1.7.0",
    "analyzers.implementations.custom_detector": "1.0.0",
}


def _git_version(module_path: str) -> str:
    rel_file = module_path.replace(".", "/") + ".py"
    abs_file = os.path.join(BASE_DIR, rel_file)
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--", abs_file],
            capture_output=True, text=True,
            cwd=BASE_DIR,
        )
        count = len([l for l in result.stdout.strip().splitlines() if l])
        if count > 0:
            return f"1.{max(count - 1, 0)}.0"
    except Exception:
        pass
    return _FALLBACK_VERSIONS.get(module_path, "1.0.0")


ANALYZERS = [
    {
        "name": "metadata",
        "analyzer_class": "analyzers.implementations.metadata_analyzer.MetadataAnalyzer",
        "weight": 2.5,
        "queue": "default",
        "timeout": 60,
    },
    {
        "name": "ela",
        "analyzer_class": "analyzers.implementations.ela_analyzer.ELAAnalyzer",
        "weight": 1.0,
        "queue": "default",
        "timeout": 60,
    },
    {
        "name": "siglip_detector",
        "analyzer_class": "analyzers.implementations.siglip_detector.SigLIPDetector",
        "weight": 2.0,
        "queue": "ml",
        "timeout": 180,
    },
    {
        "name": "npr_detector",
        "analyzer_class": "analyzers.implementations.npr_detector.NPRDetector",
        "weight": 0.5,
        "queue": "ml",
        "timeout": 180,
    },
    {
        "name": "community_forensics",
        "analyzer_class": "analyzers.implementations.community_forensics.CommunityForensicsDetector",
        "weight": 3.0,
        "queue": "ml",
        "timeout": 180,
    },
    {
        "name": "video_frame",
        "analyzer_class": "analyzers.implementations.video_analyzer.VideoFrameAnalyzer",
        "weight": 2.0,
        "queue": "ml",
        "timeout": 300,
    },
    {
        "name": "llm_text",
        "analyzer_class": "analyzers.implementations.llm_analyzer.LLMTextAnalyzer",
        "weight": 2.5,
        "queue": "ml",
        "timeout": 180,
    },
    {
        "name": "audio_spectrogram",
        "analyzer_class": "analyzers.implementations.audio_analyzer.AudioSpectrogramAnalyzer",
        "weight": 2.0,
        "queue": "ml",
        "timeout": 120,
    },
    {
        "name": "llm_vision",
        "analyzer_class": "analyzers.implementations.llm_image_analyzer.LLMImageAnalyzer",
        "weight": 1.5,
        "queue": "ml",
        "timeout": 300,
    },
    {
        "name": "custom_detector",
        "analyzer_class": "analyzers.implementations.custom_detector.CustomDetector",
        "weight": 3.5,
        "queue": "ml",
        "timeout": 180,
    },
]


class Command(BaseCommand):
    help = "Seed analyzer configurations"

    def handle(self, *args, **options):
        active_names = {a["name"] for a in ANALYZERS}
        for analyzer_data in ANALYZERS:
            module_path = analyzer_data["analyzer_class"].rsplit(".", 1)[0]
            data = {**analyzer_data, "version": _git_version(module_path)}
            obj, created = AnalyzerConfig.objects.update_or_create(
                name=data["name"],
                defaults=data,
            )
            status = "Created" if created else "Updated"
            self.stdout.write(f"{status}: {obj.name} v{obj.version}")

        stale = AnalyzerConfig.objects.exclude(name__in=active_names).filter(is_active=True)
        for config in stale:
            config.is_active = False
            config.save(update_fields=["is_active"])
            self.stdout.write(f"Deactivated: {config.name}")
