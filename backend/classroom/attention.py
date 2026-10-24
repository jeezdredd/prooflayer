from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from analyzers.models import AnalysisResult
from content.models import Submission, VerdictObjection

FLAGGED = ("fake", "likely_fake", "suspicious")
FLAGGED_VERDICTS = ("fake", "likely_fake", "suspicious", "needs_review")
COPY_ATTENTION = 85
CLEARED_VERDICT = "authentic"
TEXT_FLAGS = {
    "text_classifier": "ai_text",
    "text_grade_fit": "age",
    "text_style": "style",
    "text_citations": "sources",
    "text_shadow": "shadow",
}
CHIP_ANALYZERS = ("text_evasion", *TEXT_FLAGS)


def cleared_q() -> Q:
    changed = VerdictObjection.objects.filter(submission=OuterRef("pk"), decision=VerdictObjection.Decision.CHANGED)
    return Q(final_verdict=CLEARED_VERDICT) & Q(Exists(changed))


def signals_q() -> Q:
    flagged_check = AnalysisResult.objects.filter(
        submission=OuterRef("pk"), analyzer__name__in=CHIP_ANALYZERS, verdict__in=FLAGGED,
    )
    trace = AnalysisResult.objects.filter(submission=OuterRef("pk"), analyzer__name="metadata").filter(
        (Q(evidence__has_key="evasion") & ~Q(evidence__evasion=[]))
        | (Q(evidence__has_key="ai_trace") & ~Q(evidence__ai_trace=[]))
    )
    copy = Q(plagiarism_report__status="done", plagiarism_report__originality__lt=COPY_ATTENTION)
    return Q(Exists(flagged_check)) | Q(Exists(trace)) | copy


def attention_q() -> Q:
    return Q(status=Submission.Status.COMPLETED) & (
        Q(final_verdict__in=FLAGGED_VERDICTS) | (signals_q() & ~cleared_q())
    )


def is_cleared(submission) -> bool:
    if submission.final_verdict != CLEARED_VERDICT:
        return False
    return any(o.decision == VerdictObjection.Decision.CHANGED for o in submission.objections.all())


def class_attention(classroom_ids) -> dict:
    ids = list(classroom_ids)
    if not ids:
        return {}
    counts = {cid: {"needs_attention": 0, "open_objections": 0, "overdue_objections": 0} for cid in ids}
    flagged = (
        Submission.objects.filter(classroom_id__in=ids).filter(attention_q())
        .order_by().values_list("classroom_id").annotate(n=Count("id"))
    )
    for cid, n in flagged:
        counts[cid]["needs_attention"] = n
    objections = (
        VerdictObjection.objects.filter(submission__classroom_id__in=ids, status=VerdictObjection.Status.OPEN)
        .order_by().values_list("submission__classroom_id")
        .annotate(n=Count("id"), late=Count("id", filter=Q(due_at__lt=timezone.now())))
    )
    for cid, n, late in objections:
        counts[cid]["open_objections"] = n
        counts[cid]["overdue_objections"] = late
    return counts
