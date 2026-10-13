import logging

from celery import shared_task

from content.models import Submission

from .service import run_check

logger = logging.getLogger(__name__)


@shared_task(bind=True, soft_time_limit=600, time_limit=660)
def check_submission(self, submission_id: str):
    submission = Submission.objects.filter(id=submission_id).select_related("user").first()
    if submission is None:
        logger.info("plagiarism: submission %s gone", submission_id)
        return None
    return str(run_check(submission).id)
