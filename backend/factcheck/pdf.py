from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import HTML


VERDICT_COLORS = {
    "mostly_accurate": "#16a34a",
    "mixed": "#d97706",
    "misleading": "#dc2626",
    "no_claims": "#6b7280",
}

VERDICT_LABELS = {
    "mostly_accurate": "Mostly Accurate",
    "mixed": "Mixed Findings",
    "misleading": "Misleading",
    "no_claims": "No Claims Found",
}

ASSESSMENT_COLORS = {
    "likely_true": "#16a34a",
    "likely_false": "#dc2626",
    "uncertain": "#d97706",
}

ASSESSMENT_LABELS = {
    "likely_true": "Likely True",
    "likely_false": "Likely False",
    "uncertain": "Uncertain",
}


def render_factcheck_pdf(result: dict, original_text: str = "") -> bytes:
    verdict = result.get("overall_verdict", "no_claims")
    claims_view = []
    for c in result.get("claims", []) or []:
        a = c.get("assessment", "uncertain")
        claims_view.append({
            **c,
            "display_color": ASSESSMENT_COLORS.get(a, "#6b7280"),
            "display_label": ASSESSMENT_LABELS.get(a, "Uncertain"),
        })
    html = render_to_string("factcheck/report.html", {
        "result": result,
        "claims": claims_view,
        "entities": result.get("entities", []) or [],
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS.get(verdict, "Unknown"),
        "verdict_color": VERDICT_COLORS.get(verdict, "#6b7280"),
        "original_text": original_text,
        "generated_at": timezone.now(),
    })
    return HTML(string=html).write_pdf()
