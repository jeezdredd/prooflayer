import csv
import io

from django.utils import timezone

from common.names import display_name

from .attention import COPY_ATTENTION, is_cleared
from .serializers import latest_objection, submission_flags, submission_note

BOM = "﻿"
LANGS = ("en", "ru")
COPY_ALERT = 60
ALERT_VERDICTS = ("likely_fake", "fake")
LOOK_VERDICTS = ("needs_review", "suspicious")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text

COPY = {
    "en": {
        "delimiter": ",",
        "date": "%Y-%m-%d",
        "headers": ("Student", "Work", "Date", "Result", "What the checks found", "Matches %", "Objection"),
        "no_student": "No student (teacher check)",
        "verdicts": {
            "authentic": "Looks like the student's own work",
            "authentic_edited": "Looks like the student's own work",
            "needs_review": "Worth a closer look",
            "suspicious": "Worth a conversation with the student",
            "likely_fake": "Strong signs the student did not write this",
            "fake": "Strong signs the student did not write this",
            "inconclusive": "No clear signs of AI, but no firm answer either",
        },
        "too_short": "Too short to check for AI writing",
        "copy_alert": "Most of the text was found in other sources",
        "copy_look": "Part of the text matches other sources",
        "flags_look": "Worth a look: see what the checks found",
        "cleared": "Teacher cleared the work after an objection",
        "status": {"pending": "Waiting for the check", "processing": "Being checked", "failed": "Check failed"},
        "flags": {
            "ai_text": "chatbot text",
            "ai_trace": "AI generator trace",
            "trace_hidden": "AI trace damaged",
            "ai_image": "looks AI-generated",
            "ai_media": "looks like generated sound or video",
            "hidden_text": "hidden text in file",
            "tricks": "disguised letters",
            "shadow": "follows an AI answer",
            "copy": "matches {n}%",
            "sources": "invented sources",
            "age": "vocabulary above age",
            "style": "unlike own earlier work",
        },
        "objection_open": "waiting for an answer by {date}",
        "objection_overdue": "answer overdue since {date}",
        "objection_upheld": "verdict upheld",
        "objection_changed": "verdict changed: own work",
    },
    "ru": {
        "delimiter": ";",
        "date": "%d.%m.%Y",
        "headers": ("Ученик", "Работа", "Дата", "Итог", "Что нашли проверки", "Совпадения %", "Возражение"),
        "no_student": "Без ученика (проверка учителя)",
        "verdicts": {
            "authentic": "Похоже на самостоятельную работу ученика",
            "authentic_edited": "Похоже на самостоятельную работу ученика",
            "needs_review": "Стоит присмотреться",
            "suspicious": "Стоит поговорить с учеником",
            "likely_fake": "Серьёзные признаки, что работу писал не ученик",
            "fake": "Серьёзные признаки, что работу писал не ученик",
            "inconclusive": "Явных признаков ИИ нет, но и твёрдого ответа тоже",
        },
        "too_short": "Слишком короткий текст, чтобы проверить на ИИ",
        "copy_alert": "Большая часть текста найдена в других источниках",
        "copy_look": "Часть текста совпадает с другими источниками",
        "flags_look": "Есть на что посмотреть: см. что нашли проверки",
        "cleared": "Учитель снял подозрение после возражения",
        "status": {"pending": "Ждёт проверки", "processing": "Проверяется", "failed": "Проверка не удалась"},
        "flags": {
            "ai_text": "текст чат-бота",
            "ai_trace": "след ИИ-генератора",
            "trace_hidden": "след ИИ повреждён",
            "ai_image": "похоже на картинку нейросети",
            "ai_media": "похоже на сгенерированный звук или видео",
            "hidden_text": "скрытый текст в файле",
            "tricks": "замаскированные буквы",
            "shadow": "повторяет ИИ-ответ",
            "copy": "совпадения {n}%",
            "sources": "выдуманные источники",
            "age": "лексика не по возрасту",
            "style": "не похоже на прежние работы",
        },
        "objection_open": "ждёт ответа до {date}",
        "objection_overdue": "ответ просрочен, срок был {date}",
        "objection_upheld": "вердикт оставлен",
        "objection_changed": "вердикт изменён: работа самостоятельная",
    },
}


def pick_lang(request) -> str:
    wanted = (request.query_params.get("lang") or "").lower()
    if wanted in LANGS:
        return wanted
    own = getattr(request.user, "language", "") or ""
    if own in LANGS:
        return own
    header = request.headers.get("Accept-Language", "").lower()
    return "ru" if header.startswith("ru") else "en"


def _result(submission, flags, copy) -> str:
    if submission.status != "completed":
        return copy["status"].get(submission.status, submission.status)
    if is_cleared(submission):
        return copy["cleared"]
    verdict = submission.final_verdict if submission.final_verdict in copy["verdicts"] else "inconclusive"
    originality = _originality_value(submission)
    if verdict not in ALERT_VERDICTS and originality is not None and originality < COPY_ALERT:
        return copy["copy_alert"]
    if verdict not in ALERT_VERDICTS + LOOK_VERDICTS:
        if originality is not None and originality < COPY_ATTENTION:
            return copy["copy_look"]
        if flags:
            return copy["flags_look"]
    if verdict == "inconclusive" and submission_note(submission) == "too_short":
        return copy["too_short"]
    return copy["verdicts"][verdict]


def _originality_value(submission):
    report = getattr(submission, "plagiarism_report", None)
    if report is None or report.status != "done" or report.originality is None:
        return None
    return report.originality


def _objection(submission, copy) -> str:
    objection = latest_objection(submission)
    if objection is None:
        return ""
    if objection.status == "open":
        due = timezone.localtime(objection.due_at).strftime(copy["date"])
        return (copy["objection_overdue"] if objection.overdue else copy["objection_open"]).format(date=due)
    return copy["objection_changed"] if objection.decision == "changed" else copy["objection_upheld"]


def class_table(submissions, lang: str, unattributed) -> str:
    copy = COPY[lang if lang in LANGS else "en"]
    buf = io.StringIO()
    buf.write(BOM)
    writer = csv.writer(buf, delimiter=copy["delimiter"])
    writer.writerow(copy["headers"])
    for s in submissions:
        flags = submission_flags(s) if s.status == "completed" else []
        originality = _originality_value(s)
        matches = "" if originality is None else str(round(100 - originality))
        flag_text = ", ".join(copy["flags"][f].format(n=matches) for f in flags if f in copy["flags"])
        student = copy["no_student"] if unattributed(s) else display_name(s.user)
        writer.writerow([
            csv_safe(student),
            csv_safe(s.original_filename),
            timezone.localtime(s.created_at).strftime(copy["date"]),
            csv_safe(_result(s, flags, copy)),
            csv_safe(flag_text),
            matches,
            csv_safe(_objection(s, copy)),
        ])
    return buf.getvalue()
