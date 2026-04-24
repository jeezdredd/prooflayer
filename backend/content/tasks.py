import logging

from celery import shared_task
from django.core.files.base import ContentFile

from .models import Submission
from .services import (
    check_known_fake,
    clone_analysis_results,
    compute_perceptual_hashes,
    compute_sha256,
    extract_metadata,
    find_cached_result,
    generate_thumbnail,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def process_submission(self, submission_id):
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        logger.error("Submission %s not found", submission_id)
        return

    try:
        submission.status = Submission.Status.PROCESSING
        submission.save(update_fields=["status"])

        sha256 = compute_sha256(submission.file)
        submission.sha256_hash = sha256

        cached = find_cached_result(sha256, submission.id)
        if cached:
            submission.final_score = cached.final_score
            submission.final_verdict = cached.final_verdict
            submission.is_known_fake = cached.is_known_fake
            submission.phash = cached.phash
            submission.dhash = cached.dhash
            submission.metadata = cached.metadata
            submission.status = Submission.Status.COMPLETED
            submission.save(update_fields=[
                "sha256_hash", "final_score", "final_verdict",
                "is_known_fake", "phash", "dhash", "metadata", "status",
            ])
            clone_analysis_results(cached, submission)
            logger.info("Submission %s resolved from cache (source: %s)", submission_id, cached.id)
            return

        metadata = extract_metadata(submission.file.path)
        submission.metadata = metadata

        thumb_buffer = generate_thumbnail(submission.file.path)
        if thumb_buffer:
            thumb_name = f"thumb_{submission.id}.jpg"
            submission.thumbnail.save(thumb_name, ContentFile(thumb_buffer.read()), save=False)

        is_fake = check_known_fake(sha256)
        submission.is_known_fake = is_fake

        ph, dh = compute_perceptual_hashes(submission.file.path)
        submission.phash = ph
        submission.dhash = dh

        submission.save(update_fields=["sha256_hash", "metadata", "thumbnail", "is_known_fake", "phash", "dhash"])

        from analyzers.tasks import dispatch_analysis
        dispatch_analysis.delay(str(submission.id))

    except Exception as exc:
        logger.exception("Error processing submission %s", submission_id)
        submission.status = Submission.Status.FAILED
        submission.save(update_fields=["status"])
        raise self.retry(exc=exc)
