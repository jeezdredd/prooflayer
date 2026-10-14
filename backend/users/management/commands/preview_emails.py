from pathlib import Path

from django.core.management.base import BaseCommand

from users.mail import render
from users.mail_samples import KINDS, sample_context
from users.models import User


class Command(BaseCommand):
    help = "Render every user email to HTML files for a visual check"

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True)
        parser.add_argument("--asset-base", default="")

    def handle(self, *args, **options):
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)
        for lang in ("ru", "en"):
            user = User(email="alex@example.com", username="alex", language=lang)
            for kind in KINDS:
                context = sample_context(kind, user)
                if options["asset_base"]:
                    context["asset_base"] = options["asset_base"]
                _, html = render(context)
                path = out / f"{kind}.{lang}.html"
                path.write_text(html)
                self.stdout.write(str(path))
