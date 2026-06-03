import mimetypes
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from content.models import Submission
from content.tasks import process_submission

User = get_user_model()

SAMPLES_ROOT = Path(__file__).resolve().parents[6] / "samples" / "labeled"

LABEL_MAP = {
    "real": "real",
    "fake": "fake",
}

IMAGE_MIMES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class Command(BaseCommand):
    help = "Upload labeled samples from samples/labeled/ as Submissions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            default="",
            help="Email of user to own submissions (default: first superuser)",
        )
        parser.add_argument(
            "--dir",
            default=str(SAMPLES_ROOT),
            help="Path to labeled/ directory with real/ and fake/ subdirs",
        )
        parser.add_argument(
            "--eager",
            action="store_true",
            help="Run analysis synchronously (Celery ALWAYS_EAGER mode)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            default=True,
            help="Skip files already uploaded (matched by original_filename)",
        )

    def handle(self, *args, **options):
        labeled_dir = Path(options["dir"])
        if not labeled_dir.exists():
            self.stderr.write(f"Directory not found: {labeled_dir}")
            return

        if options["user"]:
            try:
                user = User.objects.get(email=options["user"])
            except User.DoesNotExist:
                self.stderr.write(f"User not found: {options['user']}")
                return
        else:
            user = User.objects.filter(is_superuser=True).order_by("date_joined").first()
            if not user:
                self.stderr.write("No superuser found. Create one with createsuperuser first.")
                return

        self.stdout.write(f"Uploading as: {user.email}")

        if options["eager"]:
            from django.test.utils import override_settings
            ctx = override_settings(CELERY_TASK_ALWAYS_EAGER=True)
            ctx.__enter__()

        uploaded = 0
        skipped = 0
        errors = 0

        existing_names = set()
        if options["skip_existing"]:
            existing_names = set(
                Submission.objects.filter(user=user).values_list("original_filename", flat=True)
            )

        for label, verified_label in LABEL_MAP.items():
            label_dir = labeled_dir / label
            if not label_dir.exists():
                continue

            for file_path in sorted(label_dir.iterdir()):
                if file_path.suffix.lower() not in IMAGE_MIMES:
                    continue

                if file_path.name in existing_names:
                    self.stdout.write(f"  skip  {file_path.name} (already uploaded)")
                    skipped += 1
                    continue

                mime = IMAGE_MIMES[file_path.suffix.lower()]
                try:
                    content = file_path.read_bytes()
                    uploaded_file = SimpleUploadedFile(file_path.name, content, content_type=mime)
                    submission = Submission.objects.create(
                        user=user,
                        file=uploaded_file,
                        original_filename=file_path.name,
                        mime_type=mime,
                        file_size=len(content),
                        verified_label=verified_label,
                        approved_for_training=True,
                    )
                    process_submission.delay(str(submission.id))
                    self.stdout.write(f"  ok    {file_path.name}  [{label}]  {submission.id}")
                    uploaded += 1
                except Exception as exc:
                    self.stderr.write(f"  FAIL  {file_path.name}: {exc}")
                    errors += 1

        if options["eager"]:
            ctx.__exit__(None, None, None)

        self.stdout.write(f"\nDone: {uploaded} uploaded, {skipped} skipped, {errors} errors")
