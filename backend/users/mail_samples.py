from django.conf import settings

from .mail import (
    email_change_confirm_context,
    email_change_notice_context,
    email_changed_context,
    objection_context,
    password_reset_context,
    update_context,
    verification_context,
)
from .models import ProductUpdate, User

SAMPLE_UPDATE = ProductUpdate(
    title_en="Detection got sharper this week",
    title_ru="Распознавание стало точнее",
    summary_en="A retrained image detector, a status page with live numbers and emails in your language.",
    summary_ru="Дообученный детектор изображений, страница статуса с живыми цифрами и письма на вашем языке.",
    body_en=(
        "Here is what changed in ProofLayer since the last update.\n\n"
        "- The image detector now retrains itself every week and goes live only after passing a held-out check\n"
        "- Real camera photos are no longer called AI when their metadata looks odd\n"
        "- The status page shows every service and the self-learning loop in real time\n"
        "- Emails now come in Russian or English, whichever you use on the site\n\n"
        "As always, a verdict is a reason to look closer, not a final decision. A person makes that call."
    ),
    body_ru=(
        "Вот что изменилось в ProofLayer с прошлого обновления.\n\n"
        "- Детектор изображений теперь дообучается каждую неделю и выходит в работу только после проверки на отложенной выборке\n"
        "- Настоящие фото с камеры больше не помечаются как ИИ из-за странных метаданных\n"
        "- Страница статуса показывает все сервисы и самообучение в реальном времени\n"
        "- Письма теперь приходят на русском или английском, на том языке, что вы выбрали на сайте\n\n"
        "Как и раньше, вердикт это повод присмотреться, а не окончательное решение. Решение принимает человек."
    ),
    cta_label_en="See what is new",
    cta_label_ru="Посмотреть, что нового",
    cta_url="https://prooflayer.cloud/status",
)

KINDS = ("verify", "password_reset", "email_change_confirm", "email_change_notice", "email_changed", "objection", "update")
SAMPLE_NEW_EMAIL = "new.address@example.com"


def sample_context(kind: str, user, update: ProductUpdate | None = None) -> dict:
    lang = user.language if user.language in ("en", "ru") else "en"
    site = settings.FRONTEND_URL
    if kind == "verify":
        return verification_context(user, f"{site}/verify-email?token=test")
    if kind == "password_reset":
        return password_reset_context(user, f"{site}/forgot-password")
    if kind == "email_change_confirm":
        return email_change_confirm_context(user, f"{site}/confirm-email?token=test")
    if kind == "email_change_notice":
        return email_change_notice_context(user, user.email, SAMPLE_NEW_EMAIL)
    if kind == "email_changed":
        changed = User(email=SAMPLE_NEW_EMAIL, username=user.username, language=user.language)
        return email_changed_context(changed, user.email)
    if kind == "objection":
        return objection_context(
            lang=lang,
            student="Sam L.",
            title="essay-history.docx",
            classroom="History 10B",
            reason="Я писал это сам, черновики есть в Google Docs." if lang == "ru" else "I wrote this myself, my drafts are in Google Docs.",
            due="17.10.2026 18:00" if lang == "ru" else "Oct 17, 2026 18:00",
            link=f"{site}/dashboard",
        )
    return update_context(update or SAMPLE_UPDATE, user)
