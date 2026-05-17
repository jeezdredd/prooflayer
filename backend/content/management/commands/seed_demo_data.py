import io
import random
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image

from analyzers.models import AnalysisResult, AnalyzerConfig
from content.models import KnownFakeHash, Submission
from users.models import User


DEMO_SUBMISSIONS = [
    {
        "filename": "press_release_photo.jpg",
        "verdict": "authentic",
        "score": 0.12,
        "is_known_fake": False,
        "color": (160, 180, 200),
    },
    {
        "filename": "viral_protest_image.jpg",
        "verdict": "fake",
        "score": 0.87,
        "is_known_fake": True,
        "known_hash": "3b1f9c4d2e8a7b6f5c4d3e2a1b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c",
        "color": (220, 80, 60),
    },
    {
        "filename": "leaked_document_screenshot.png",
        "verdict": "suspicious",
        "score": 0.58,
        "is_known_fake": False,
        "color": (240, 240, 230),
    },
    {
        "filename": "ai_generated_celebrity.png",
        "verdict": "fake",
        "score": 0.91,
        "is_known_fake": True,
        "known_hash": "7e2c8f4a1b9d3e5c6a8f2b1d4e7c9a3b5d8e1f2a4c6b8d0e3f5a7c9b1d2e4f6a",
        "color": (180, 130, 90),
    },
    {
        "filename": "field_report_audio.wav",
        "verdict": "inconclusive",
        "score": 0.50,
        "is_known_fake": False,
        "color": (40, 50, 70),
    },
    {
        "filename": "candidate_speech_clip.mp4",
        "verdict": "needs_review",
        "score": 0.62,
        "is_known_fake": False,
        "color": (80, 90, 110),
    },
    {
        "filename": "natural_disaster_photo.jpg",
        "verdict": "fake",
        "score": 0.78,
        "is_known_fake": True,
        "known_hash": "9d4f1c7a3e8b6d2f5c9a1e4b7d0f3c6a9e2b5d8f1c4a7e0b3d6f9c2a5e8b1d4f",
        "color": (200, 100, 50),
    },
    {
        "filename": "verified_news_photo.jpg",
        "verdict": "authentic",
        "score": 0.18,
        "is_known_fake": False,
        "color": (120, 140, 160),
    },
    {
        "filename": "blurry_phone_photo.jpg",
        "verdict": "likely_fake",
        "score": 0.71,
        "is_known_fake": False,
        "color": (90, 70, 80),
    },
    {
        "filename": "satellite_imagery_test.png",
        "verdict": "fake",
        "score": 0.83,
        "is_known_fake": True,
        "known_hash": "2e7c4a1f8b5d9c3e6a0f2b8d4c7e1a5f9b3d6c0e2a8f4b1d7c5e9a3f0b6d2c8e",
        "color": (60, 80, 60),
    },
]

ANALYZER_RESULTS = {
    "authentic": [
        ("metadata", "authentic", 0.85, {"flags": [], "ai_tool": {"detected": False}}),
        ("ela", "authentic", 0.75, {"uniformity_ratio": 0.92, "max_error": 18}),
        ("ai_detector", "authentic", 0.85, {"ai_probability_avg": 0.12, "ensemble_size": 3}),
        ("llm_vision", "authentic", 0.6, {"reasoning": "Natural lighting, consistent texture, no obvious AI artifacts."}),
    ],
    "suspicious": [
        ("metadata", "suspicious", 0.6, {"flags": ["editing_software"], "ai_tool": {"tool": "Photoshop", "detected": True}}),
        ("ela", "suspicious", 0.7, {"uniformity_ratio": 0.65, "max_error": 78}),
        ("ai_detector", "inconclusive", 0.5, {"ai_probability_avg": 0.42}),
        ("llm_vision", "inconclusive", 0.5, {"reasoning": "Some texture inconsistencies, hard to determine without more context."}),
    ],
    "likely_fake": [
        ("metadata", "suspicious", 0.7, {"flags": ["metadata_stripped"]}),
        ("ela", "suspicious", 0.75, {"uniformity_ratio": 0.4, "max_error": 142}),
        ("ai_detector", "suspicious", 0.7, {"ai_probability_avg": 0.65, "ai_models_voting_fake": 2}),
        ("llm_vision", "fake", 0.6, {"reasoning": "Smooth skin texture, uncanny valley features, soft background."}),
    ],
    "fake": [
        ("metadata", "suspicious", 0.7, {"flags": ["metadata_stripped"], "ai_tool": {"tool": "Stable Diffusion", "detected": True}}),
        ("ela", "fake", 0.85, {"uniformity_ratio": 0.22, "max_error": 240}),
        ("ai_detector", "fake", 0.9, {"ai_probability_avg": 0.89, "ai_models_voting_fake": 3}),
        ("llm_vision", "fake", 0.6, {"reasoning": "Clear AI generation artifacts: warped fingers, incoherent text in background, plastic skin."}),
    ],
    "needs_review": [
        ("metadata", "authentic", 0.7, {}),
        ("ai_detector", "fake", 0.7, {"ai_probability_avg": 0.61}),
        ("ela", "authentic", 0.6, {}),
        ("llm_vision", "inconclusive", 0.5, {"reasoning": "Mixed signals."}),
    ],
    "inconclusive": [
        ("metadata", "inconclusive", 0.5, {"flags": ["metadata_stripped"]}),
        ("ela", "inconclusive", 0.5, {"note": "lossless source"}),
        ("ai_detector", "inconclusive", 0.5, {"note": "non-photographic content"}),
        ("llm_vision", "inconclusive", 0.5, {"reasoning": "Cannot determine."}),
    ],
}


def make_demo_image(color: tuple, idx: int) -> SimpleUploadedFile:
    img = Image.new("RGB", (640, 480), color=color)
    for _ in range(20):
        x = random.randint(0, 640)
        y = random.randint(0, 480)
        c = (
            min(255, color[0] + random.randint(-30, 30)),
            min(255, color[1] + random.randint(-30, 30)),
            min(255, color[2] + random.randint(-30, 30)),
        )
        for dx in range(20):
            for dy in range(20):
                if 0 <= x + dx < 640 and 0 <= y + dy < 480:
                    img.putpixel((x + dx, y + dy), c)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return SimpleUploadedFile(f"demo_{idx}.jpg", buf.read(), content_type="image/jpeg")


class Command(BaseCommand):
    help = "Seed demo submissions with realistic verdicts and analyzer results"

    def add_arguments(self, parser):
        parser.add_argument("--user", type=str, default=None, help="Email of user to attach submissions to (default: first staff)")
        parser.add_argument("--clear", action="store_true", help="Delete existing user demo submissions first")

    def handle(self, *args, **opts):
        if opts["user"]:
            user = User.objects.filter(email=opts["user"]).first()
        else:
            user = User.objects.filter(is_staff=True).first() or User.objects.first()

        if not user:
            self.stdout.write(self.style.ERROR("No user found. Create one first."))
            return

        self.stdout.write(f"Seeding demo data for user: {user.email}")

        from django.core.management import call_command
        call_command("seed_known_fakes")

        if opts["clear"]:
            demo_names = [s["filename"] for s in DEMO_SUBMISSIONS]
            count, _ = Submission.objects.filter(user=user, original_filename__in=demo_names).delete()
            self.stdout.write(f"Cleared {count} previous demo submissions")

        analyzer_configs = {cfg.name: cfg for cfg in AnalyzerConfig.objects.all()}
        if not analyzer_configs:
            self.stdout.write(self.style.WARNING("No analyzer configs found. Run seed_analyzers first."))
            return

        now = timezone.now()
        created = 0
        for i, spec in enumerate(DEMO_SUBMISSIONS):
            file = make_demo_image(spec["color"], i)
            sub = Submission.objects.create(
                user=user,
                file=file,
                original_filename=spec["filename"],
                mime_type="image/jpeg",
                file_size=file.size,
                sha256_hash=spec.get("known_hash") or f"demo{'%064x' % random.getrandbits(256)}"[:64],
                status=Submission.Status.COMPLETED,
                final_score=spec["score"],
                final_verdict=spec["verdict"],
                is_known_fake=spec["is_known_fake"],
                created_at=now - timedelta(hours=i * 6, minutes=random.randint(0, 59)),
            )
            Submission.objects.filter(id=sub.id).update(created_at=now - timedelta(hours=i * 6))

            for analyzer_name, verdict, confidence, evidence in ANALYZER_RESULTS[spec["verdict"]]:
                cfg = analyzer_configs.get(analyzer_name)
                if not cfg:
                    continue
                AnalysisResult.objects.create(
                    submission=sub,
                    analyzer=cfg,
                    confidence=confidence,
                    verdict=verdict,
                    evidence=evidence,
                    execution_time=random.uniform(0.1, 12.0),
                )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} demo submissions for {user.email}"))
        self.stdout.write(f"Known-fake submissions: {Submission.objects.filter(user=user, is_known_fake=True).count()}")
        self.stdout.write(f"Total submissions: {Submission.objects.filter(user=user).count()}")
