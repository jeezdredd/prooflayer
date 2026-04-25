import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def run_provenance_check(submission_id):
    from content.models import Submission
    from .services import extract_c2pa, run_google_vision_search, run_phash_lookup, run_tineye_search

    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        logger.error("Submission %s not found for provenance check", submission_id)
        return

    run_phash_lookup(submission)
    run_tineye_search(submission)
    run_google_vision_search(submission)
    extract_c2pa(submission)
    logger.info("Provenance check complete for submission %s", submission_id)
