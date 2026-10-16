from django.db import migrations

SHIPPED = ("Text detector v2", "Faster vision judge on our GPU", "Highlighted passages in essays")

NEW_ITEMS = (
    (
        10,
        "building",
        "Humanizer-proof text check",
        "Text run through a humanizer or a paraphrasing service is caught as reliably as plain AI text. We train on the "
        "output of two dozen commercial humanizers and attack our own detector with rewrites built to slip past it. "
        "Character tricks, cut-out Content Credentials and damaged generator watermarks are already reported as an "
        "attempt to hide AI traces.",
        "Текст после «хуманайзеров»",
        "Текст, прогнанный через «хуманайзер» или сервис перефразирования, ловится так же надёжно, как обычный текст "
        "ИИ. Мы обучаемся на выдаче двух десятков коммерческих «хуманайзеров» и атакуем собственный детектор "
        "переписанными текстами, созданными, чтобы его обойти. Подмена символов, вырезанные Content Credentials и "
        "повреждённые водяные знаки генераторов уже отмечаются как попытка скрыть следы ИИ.",
    ),
    (
        20,
        "building",
        "Manipulation map",
        "Shows where an image was changed, not only whether: the area an AI filled in, a swapped face, a pasted object, "
        "highlighted on the picture with a score for each region. It sits next to the provenance panel that already "
        "reads Content Credentials and generator watermarks and links to Google's SynthID check.",
        "Карта правок",
        "Показывает, где изображение изменили, а не только было ли это: область, дорисованную ИИ, заменённое лицо, "
        "вклеенный объект, с оценкой для каждой области прямо на картинке. Она появится рядом с панелью "
        "происхождения, которая уже читает Content Credentials и водяные знаки генераторов и ведёт на проверку "
        "SynthID от Google.",
    ),
    (
        30,
        "exploring",
        "Document forgery check",
        "Edited PDFs, scans and screenshots: diplomas, certificates, bank statements, invoices, chat screenshots. We look "
        "for added layers, mismatched fonts on one line, pasted pieces of a scan, metadata that does not add up and "
        "generated stamps or signatures.",
        "Проверка документов на подделку",
        "Отредактированные PDF, сканы и скриншоты: дипломы, справки, банковские выписки, счета, скриншоты переписки. "
        "Ищем дописанные слои, разные шрифты в одной строке, вставленные куски скана, несходящиеся метаданные, "
        "сгенерированные печати и подписи.",
    ),
    (
        40,
        "exploring",
        "Image history",
        "Where and when a picture first appeared online and how it changed on the way: the original, the crops, the "
        "edits. Built on the perceptual fingerprints we already keep for every upload.",
        "История изображения",
        "Где и когда картинка впервые появилась в сети и как менялась по пути: оригинал, обрезки, правки. Строится на "
        "перцептивных отпечатках, которые мы уже сохраняем для каждой загрузки.",
    ),
    (
        50,
        "exploring",
        "AI music check",
        "Tracks from Suno, Udio and other music generators told apart from recorded music, for labels, platforms, "
        "contests and streamers.",
        "Проверка музыки на ИИ",
        "Отличаем треки из Suno, Udio и других музыкальных генераторов от записанной музыки: для лейблов, площадок, "
        "конкурсов и стримеров.",
    ),
)

POSITIONS = {
    "More languages for text checks": 60,
    "Authorship Passport": 70,
    "Live Call Guard": 80,
    "Model Fingerprint": 90,
    "Tribunal 2.0": 100,
}

PASSPORT_EN = (
    "Every student builds a record of how they really write. Each new essay is checked along five lines: how it was "
    "typed and revised, whether its argument matches a hundred AI answers to the same assignment, whether its sources "
    "exist, whether it fits the student's own baseline, and whether it mirrors classmates' work. Work handed in on "
    "paper or by email joins the same record once the teacher uploads it, together with a few questions for a short "
    "oral check. Teachers see which lines agree, with the exact passages, not a single percentage."
)
PASSPORT_RU = (
    "У каждого ученика складывается картина того, как он на самом деле пишет. Каждое новое сочинение проверяется по "
    "пяти линиям: как оно набиралось и правилось, совпадает ли его аргументация с сотней ответов ИИ на то же задание, "
    "существуют ли его источники, соответствует ли оно собственному уровню ученика и не повторяет ли работы "
    "одноклассников. Работы, сданные на бумаге или по почте, попадают туда же, когда учитель их загрузит, вместе с "
    "несколькими вопросами для короткой устной проверки. Учитель видит, какие линии сходятся, с конкретными "
    "фрагментами, а не один процент."
)


def refresh(apps, schema_editor):
    RoadmapItem = apps.get_model("api", "RoadmapItem")
    RoadmapItem.objects.filter(title__in=SHIPPED).update(is_published=False)
    for title, position in POSITIONS.items():
        RoadmapItem.objects.filter(title=title).update(position=position)
    RoadmapItem.objects.filter(title="Authorship Passport").update(body=PASSPORT_EN, body_ru=PASSPORT_RU)
    for position, status, title, body, title_ru, body_ru in NEW_ITEMS:
        if not RoadmapItem.objects.filter(title=title).exists():
            RoadmapItem.objects.create(
                position=position, status=status, title=title, body=body, title_ru=title_ru, body_ru=body_ru,
            )


def restore(apps, schema_editor):
    RoadmapItem = apps.get_model("api", "RoadmapItem")
    RoadmapItem.objects.filter(title__in=SHIPPED).update(is_published=True)
    RoadmapItem.objects.filter(title__in=[item[2] for item in NEW_ITEMS]).delete()


class Migration(migrations.Migration):
    dependencies = [("api", "0008_roadmap_vision_gpu_beta")]
    operations = [migrations.RunPython(refresh, restore)]
