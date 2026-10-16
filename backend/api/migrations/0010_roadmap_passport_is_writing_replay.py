from django.db import migrations

PASSPORT = "Authorship Passport"
REPLAY = "Writing replay"

REPLAY_EN = (
    "The last missing line of the authorship check: a record of how a text was actually written. Students type in "
    "ProofLayer, and the teacher can replay the essay as it grew, with pauses, rewrites and the moments a large block "
    "was pasted in. The other lines already run in Classroom: comparison with AI answers to the same assignment, "
    "sources that do not exist, the student's own level and style, and essays that mirror classmates' work."
)
REPLAY_RU = (
    "Последняя недостающая линия проверки авторства: запись того, как текст на самом деле писался. Ученик пишет "
    "прямо в ProofLayer, а учитель может воспроизвести, как сочинение росло: паузы, переписывания и моменты, когда "
    "вставили большой кусок. Остальные линии уже работают в Classroom: сравнение с ответами ИИ на то же задание, "
    "несуществующие источники, собственный уровень и стиль ученика и сочинения, повторяющие работы одноклассников."
)

FINGERPRINT_EN = (
    "Not just \"AI or not\" but which model made it: GPT, Claude, Gemini or Llama for text, Flux, Midjourney or Sora "
    "for images and video, with a confidence for every family. Signed files and decoded watermarks already name their "
    "generator; the rest is attribution from the content itself."
)
FINGERPRINT_RU = (
    "Не просто «ИИ или нет», а какая модель это сделала: GPT, Claude, Gemini или Llama для текста, Flux, Midjourney или "
    "Sora для изображений и видео, с уверенностью для каждого семейства. Подписанные файлы и расшифрованные водяные "
    "знаки уже называют свой генератор; остальное предстоит определять по самому содержимому."
)


def forward(apps, schema_editor):
    RoadmapItem = apps.get_model("api", "RoadmapItem")
    RoadmapItem.objects.filter(title=PASSPORT).update(
        title=REPLAY, title_ru="Запись процесса письма", body=REPLAY_EN, body_ru=REPLAY_RU,
    )
    RoadmapItem.objects.filter(title="Model Fingerprint").update(body=FINGERPRINT_EN, body_ru=FINGERPRINT_RU)


def backward(apps, schema_editor):
    RoadmapItem = apps.get_model("api", "RoadmapItem")
    RoadmapItem.objects.filter(title=REPLAY).update(title=PASSPORT, title_ru="Паспорт авторства")


class Migration(migrations.Migration):
    dependencies = [("api", "0009_roadmap_october_refresh")]
    operations = [migrations.RunPython(forward, backward)]
