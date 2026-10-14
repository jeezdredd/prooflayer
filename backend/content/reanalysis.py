from django.core.cache import cache

from analyzers.models import AnalysisResult
from analyzers.tasks import AGGREGATION_LOCK_KEY, dispatch_analysis

from .models import Submission

REANALYZABLE_STATUSES = (Submission.Status.COMPLETED, Submission.Status.FAILED)


def can_reanalyze(submission: Submission) -> bool:
    return submission.status in REANALYZABLE_STATUSES and bool(submission.file)


def restart_analysis(submission: Submission) -> None:
    AnalysisResult.objects.filter(submission=submission).delete()
    cache.delete(AGGREGATION_LOCK_KEY.format(submission_id=submission.id))
    submission.status = Submission.Status.PROCESSING
    submission.final_score = None
    submission.final_verdict = ""
    submission.status_message = "Re-analyzing with current Tribunal..."
    submission.save(update_fields=["status", "final_score", "final_verdict", "status_message"])
    dispatch_analysis.delay(str(submission.id))
