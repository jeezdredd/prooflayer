import json
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from users.models import ProductUpdate

from .models import ChangelogEntry

SOURCE = Path(__file__).with_name("changelog.json")

DIGEST_COPY = {
    "en": {
        "title": "What's new in ProofLayer",
        "summary": "{count} changes since the last update.",
        "intro": "Here is what changed in ProofLayer recently.",
        "outro": "As always, a verdict is a reason to look closer, not a final decision. A person makes that call.",
        "cta": "See every change",
    },
    "ru": {
        "title": "Что нового в ProofLayer",
        "summary": "{count} изменений с прошлого письма.",
        "intro": "Вот что изменилось в ProofLayer за последнее время.",
        "outro": "Как и раньше, вердикт это повод присмотреться, а не окончательное решение. Решение принимает человек.",
        "cta": "Все изменения",
    },
}


def load_source(path: Path = SOURCE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@transaction.atomic
def sync(path: Path = SOURCE) -> tuple[int, int]:
    created = updated = 0
    for item in load_source(path):
        values = {
            "date": item["date"],
            "kind": item.get("kind", ChangelogEntry.Kind.FEATURE),
            "title_en": item["title"]["en"],
            "title_ru": item["title"]["ru"],
            "body_en": item.get("body", {}).get("en", ""),
            "body_ru": item.get("body", {}).get("ru", ""),
        }
        _, was_created = ChangelogEntry.objects.update_or_create(slug=item["slug"], defaults=values)
        created += was_created
        updated += not was_created
    return created, updated


def pending_entries():
    return ChangelogEntry.objects.filter(is_published=True, digest__isnull=True, date__lte=timezone.localdate()).order_by("date", "created_at")


def _bullets(entries, lang: str) -> str:
    lines = []
    for entry in entries:
        title = entry.title_ru if lang == "ru" else entry.title_en
        body = entry.body_ru if lang == "ru" else entry.body_en
        lines.append(f"- {title}. {body}".strip() if body else f"- {title}")
    return "\n".join(lines)


@transaction.atomic
def draft_digest() -> ProductUpdate | None:
    entries = list(pending_entries())
    if not entries:
        return None
    en, ru = DIGEST_COPY["en"], DIGEST_COPY["ru"]
    update = ProductUpdate.objects.create(
        title_en=en["title"],
        title_ru=ru["title"],
        summary_en=en["summary"].format(count=len(entries)),
        summary_ru=ru["summary"].format(count=len(entries)),
        body_en=f"{en['intro']}\n\n{_bullets(entries, 'en')}\n\n{en['outro']}",
        body_ru=f"{ru['intro']}\n\n{_bullets(entries, 'ru')}\n\n{ru['outro']}",
        cta_label_en=en["cta"],
        cta_label_ru=ru["cta"],
        cta_url=f"{settings.FRONTEND_URL}/changelog",
    )
    ChangelogEntry.objects.filter(pk__in=[e.pk for e in entries]).update(digest=update)
    return update
