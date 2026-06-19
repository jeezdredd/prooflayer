import logging
from PIL import Image

from django.core.management.base import BaseCommand

from analyzers.implementations.clip_detector import _load_model as _load_clip, ENSEMBLE_MODELS as CLIP_MODELS
from analyzers.implementations.community_forensics import _load as _load_cf
from analyzers.implementations.npr_detector import _load as _load_npr
from analyzers.implementations.siglip_detector import _load as _load_siglip

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Pre-download HF models for torch analyzers so first user submission is fast"

    def handle(self, *args, **opts):
        self.stdout.write("preloading torch analyzer models...")
        targets = [
            ("siglip_detector", _load_siglip),
            ("community_forensics", _load_cf),
            ("npr_detector", _load_npr),
        ]
        for name, fn in targets:
            try:
                self.stdout.write(f"  loading {name}...")
                fn()
                self.stdout.write(self.style.SUCCESS(f"  {name} ready"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  {name} failed: {exc}"))

        for clip_name in CLIP_MODELS:
            try:
                self.stdout.write(f"  loading clip:{clip_name}...")
                _load_clip(clip_name)
                self.stdout.write(self.style.SUCCESS(f"  clip:{clip_name} ready"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  clip:{clip_name} failed: {exc}"))

        self.stdout.write(self.style.SUCCESS("preload done"))
