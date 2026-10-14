import base64
from pathlib import Path

from django.template.loader import render_to_string
from django.utils import timezone

from .copy import COPY, lang_or_default

try:
    from weasyprint import HTML
except OSError:
    HTML = None

BASE_DIR = Path(__file__).resolve().parent


def shared_context(lang: str, report_title: str, case_ref: str) -> dict:
    lang = lang_or_default(lang)
    c = COPY[lang]
    now = timezone.now()
    return {
        "lang": lang,
        "c": c,
        "title": f"ProofLayer · {report_title}",
        "report_title": report_title,
        "case_label": c["case"],
        "case_ref": case_ref,
        "generated_label": c["generated"],
        "generated_at": now.strftime("%d.%m.%Y %H:%M UTC") if lang == "ru" else now.strftime("%b %d, %Y %H:%M UTC"),
        "footer_line": c["footer"],
        "page_word": c["page"],
        "of_word": c["of"],
    }


def image_data_uri(field) -> str:
    if not field:
        return ""
    try:
        with field.open("rb") as handle:
            data = handle.read()
    except (OSError, ValueError):
        return ""
    if not data:
        return ""
    mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/webp" if data[8:12] == b"WEBP" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def render_html(template: str, context: dict) -> str:
    return render_to_string(template, context)


def render_pdf(template: str, context: dict) -> bytes:
    if HTML is None:
        raise RuntimeError("WeasyPrint system libraries are not available")
    html = render_html(template, context)
    return HTML(string=html, base_url=str(BASE_DIR) + "/").write_pdf()
