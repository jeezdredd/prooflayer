import io
from django.template.loader import render_to_string
from django.utils import timezone


def generate_report_pdf(submission, request=None):
    analysis_results = list(submission.analysis_results.select_related("analyzer").all())
    provenance_results = list(submission.provenance_results.all()) if hasattr(submission, "provenance_results") else []
    factcheck = getattr(submission, "factcheck_result", None)

    verdict_colors = {
        "authentic": "#16a34a",
        "fake": "#dc2626",
        "suspicious": "#d97706",
        "inconclusive": "#6b7280",
    }

    score = submission.final_score
    score_pct = round((score or 0) * 100, 1)
    verdict = submission.final_verdict or "inconclusive"
    verdict_color = verdict_colors.get(verdict, "#6b7280")

    file_url = None
    if submission.file and request:
        file_url = request.build_absolute_uri(submission.file.url)

    thumbnail_url = None
    if submission.thumbnail and request:
        thumbnail_url = request.build_absolute_uri(submission.thumbnail.url)

    html = render_to_string("content/report.html", {
        "submission": submission,
        "analysis_results": analysis_results,
        "provenance_results": provenance_results,
        "factcheck": factcheck,
        "score_pct": score_pct,
        "verdict": verdict,
        "verdict_color": verdict_color,
        "file_url": file_url,
        "thumbnail_url": thumbnail_url,
        "generated_at": timezone.now(),
    })

    from weasyprint import HTML
    pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/") if request else "/").write_pdf()
    return io.BytesIO(pdf_bytes)
