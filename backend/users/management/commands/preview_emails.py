from pathlib import Path

from django.core.management.base import BaseCommand

from users.mail import (
    objection_context,
    password_reset_context,
    render,
    update_context,
    verification_context,
)
from users.models import ProductUpdate, User

SAMPLE_UPDATE = ProductUpdate(
    title_en="Detection got sharper this week",
    title_ru="Распознавание стало точнее",
    summary_en="A retrained image detector, a status page with live numbers and emails in your language.",
    summary_ru="Дообученный детектор изображений, страница статуса с живыми цифрами и письма на вашем языке.",
    body_en=(
        "Here is what changed in ProofLayer since the last update.\n\n"
        "- The image detector retrained itself on fresh generator output and passed the held-out check before going live\n"
        "- Real camera photos are no longer called AI when their metadata looks odd\n"
        "- The status page shows every service and the self-learning loop in real time\n"
        "- Emails now come in Russian or English, whichever you use on the site\n\n"
        "As always, a verdict is a reason to look closer, not a final decision. A person makes that call."
    ),
    body_ru=(
        "Вот что изменилось в ProofLayer с прошлого обновления.\n\n"
        "- Детектор изображений дообучился на свежих картинках генераторов и прошёл проверку на отложенной выборке перед запуском\n"
        "- Настоящие фото с камеры больше не помечаются как ИИ из-за странных метаданных\n"
        "- Страница статуса показывает все сервисы и самообучение в реальном времени\n"
        "- Письма теперь приходят на русском или английском, на том языке, что вы выбрали на сайте\n\n"
        "Как и раньше, вердикт это повод присмотреться, а не окончательное решение. Решение принимает человек."
    ),
    cta_label_en="See what is new",
    cta_label_ru="Посмотреть, что нового",
    cta_url="https://prooflayer.cloud/status",
)


class Command(BaseCommand):
    help = "Render every user email to HTML files for a visual check"

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True)
        parser.add_argument("--asset-base", default="")

    def handle(self, *args, **options):
        out = Path(options["out"])
        out.mkdir(parents=True, exist_ok=True)
        written = []
        for lang in ("ru", "en"):
            user = User(email="alex@example.com", username="alex", language=lang)
            due = "17.10.2026 18:00" if lang == "ru" else "Oct 17, 2026 18:00"
            contexts = {
                "verify": verification_context(user, "https://prooflayer.cloud/verify-email?token=sample"),
                "password_reset": password_reset_context(user, "https://prooflayer.cloud/reset-password?uid=MQ&token=sample"),
                "objection": objection_context(
                    lang=lang,
                    student="Sam L.",
                    title="essay-history.docx",
                    classroom="History 10B",
                    reason="Я писал это сам, черновики есть в Google Docs." if lang == "ru" else "I wrote this myself, my drafts are in Google Docs.",
                    due=due,
                    link="https://prooflayer.cloud/results/sample",
                ),
                "update": update_context(SAMPLE_UPDATE, user),
            }
            for name, context in contexts.items():
                if options["asset_base"]:
                    context["asset_base"] = options["asset_base"]
                _, html = render(context)
                path = out / f"{name}.{lang}.html"
                path.write_text(html)
                written.append(path)
        for path in written:
            self.stdout.write(str(path))
