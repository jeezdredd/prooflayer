import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def run_provenance_check(submission_id):
    from content.models import Submission
    from .services import run_google_vision_search, run_tineye_search

    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        logger.error("Submission %s not found for provenance check", submission_id)
        return

    run_tineye_search(submission)
    run_google_vision_search(submission)
    logger.info("External provenance check complete for submission %s", submission_id)
