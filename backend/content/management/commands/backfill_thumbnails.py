from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from content.models import Submission
from content.services import generate_thumbnail


class Command(BaseCommand):
    help = "Regenerate thumbnails for submissions missing one"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="0 = all")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        qs = Submission.objects.filter(thumbnail="").exclude(file="")
        if options["limit"] > 0:
            qs = qs[: options["limit"]]

        total = qs.count() if options["limit"] == 0 else len(qs)
        self.stdout.write(f"backfilling {total} submissions")

        ok = 0
        skipped = 0
        failed = 0
        for sub in qs.iterator():
            if not sub.mime_type or not sub.mime_type.startswith("image/"):
                skipped += 1
                continue
            try:
                path = sub.file.path
            except Exception:
                skipped += 1
                continue

            buf = generate_thumbnail(path)
            if buf is None:
                failed += 1
                self.stdout.write(self.style.WARNING(f"  skip {sub.id} (thumbnail gen returned None)"))
                continue

            if options["dry_run"]:
                ok += 1
                continue

            name = f"{sub.id}.jpg"
            sub.thumbnail.save(name, ContentFile(buf.read()), save=False)
            sub.save(update_fields=["thumbnail"])
            ok += 1
            self.stdout.write(f"  ok {sub.id}")

        self.stdout.write(self.style.SUCCESS(f"done: ok={ok} skipped={skipped} failed={failed}"))
