from django.core.management.base import BaseCommand

from content.models import KnownFakeHash


SEED_HASHES = [
    {
        "sha256_hash": "3b1f9c4d2e8a7b6f5c4d3e2a1b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c",
        "source": "Reuters Fact Check",
        "description": "Fabricated photo of public figure circulated on Twitter, March 2026",
    },
    {
        "sha256_hash": "a8f3c2e1d9b7c6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1",
        "source": "BBC Verify",
        "description": "Deepfake video frame, Russia/Ukraine misinformation campaign",
    },
    {
        "sha256_hash": "7e2c8f4a1b9d3e5c6a8f2b1d4e7c9a3b5d8e1f2a4c6b8d0e3f5a7c9b1d2e4f6a",
        "source": "Snopes",
        "description": "Synthetic celebrity endorsement image, removed from Instagram 2025-11",
    },
    {
        "sha256_hash": "4c9e1a3f8b2d6c5e7a9f1b4d8c2e5a7f9b1d3c6e8a2f5b9d1c4e7a0f3b6c9d2e",
        "source": "AFP Fact Check",
        "description": "AI-generated 'protest' image used in viral Telegram channel",
    },
    {
        "sha256_hash": "1f5b2c9e4a7d3f6b8c1e5a9d2f4b7c0e3a6d9f2b5c8e1a4d7f0b3c6e9a2d5f8b",
        "source": "PolitiFact",
        "description": "Manipulated quote screenshot attributed to politician, 2026 election cycle",
    },
    {
        "sha256_hash": "9d4f1c7a3e8b6d2f5c9a1e4b7d0f3c6a9e2b5d8f1c4a7e0b3d6f9c2a5e8b1d4f",
        "source": "Lead Stories",
        "description": "Stable Diffusion XL render of fictional natural disaster, miscaptioned as real event",
    },
    {
        "sha256_hash": "6a3b9c1f4d7e2c5a8b1d4e7f0c3a6b9d2e5f8c1a4b7d0e3f6c9a2b5d8e1c4a7b",
        "source": "Full Fact",
        "description": "Doctored historical photograph, EXIF stripped, propagated on Reddit",
    },
    {
        "sha256_hash": "2e7c4a1f8b5d9c3e6a0f2b8d4c7e1a5f9b3d6c0e2a8f4b1d7c5e9a3f0b6d2c8e",
        "source": "Demagog",
        "description": "Generative AI fake satellite image of military deployment",
    },
]


class Command(BaseCommand):
    help = "Seed KnownFakeHash registry with example confirmed-fake entries for demo purposes."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete existing entries first")

    def handle(self, *args, **opts):
        if opts["clear"]:
            deleted, _ = KnownFakeHash.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing entries"))

        created = 0
        skipped = 0
        for entry in SEED_HASHES:
            obj, was_created = KnownFakeHash.objects.get_or_create(
                sha256_hash=entry["sha256_hash"],
                defaults={"source": entry["source"], "description": entry["description"]},
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} known-fake hashes ({skipped} already existed)"))
        self.stdout.write(f"Total in registry: {KnownFakeHash.objects.count()}")
