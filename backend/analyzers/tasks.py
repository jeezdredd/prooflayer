import logging
import time

from asgiref.sync import async_to_sync
from celery import chord, group, shared_task
from celery.exceptions import SoftTimeLimitExceeded
from channels.layers import get_channel_layer

from content.models import Submission
from content.storage_utils import local_file

from .aggregator import aggregate
from .models import AnalyzerConfig, AnalysisResult
from .registry import load_analyzer_class

logger = logging.getLogger(__name__)


def _publish_status(submission_id, status_message="", status=None, final_score=None, final_verdict=None, event=None, analyzer=None, verdict=None):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = {"type": "status"}
    if status_message:
        payload["status_message"] = status_message
    if status is not None:
        payload["status"] = status
    if final_score is not None:
        payload["final_score"] = final_score
    if final_verdict is not None:
        payload["final_verdict"] = final_verdict
    if event is not None:
        payload["event"] = event
    if analyzer is not None:
        payload["analyzer"] = analyzer
    if verdict is not None:
        payload["verdict"] = verdict
    try:
        async_to_sync(channel_layer.group_send)(
            f"submission_{submission_id}",
            {"type": "submission.update", "payload": payload},
        )
    except Exception as exc:
        logger.debug("WS publish failed (non-critical): %s", exc)

ANALYZER_STATUS_MESSAGES = {
    "metadata": "Analyzing metadata and EXIF...",
    "ela": "Checking image integrity (ELA)...",
    "ai_detector": "Running AI image detector...",
    "llm_vision": "Analyzing image with vision AI...",
    "video_frame": "Extracting and analyzing video frames...",
    "audio_spectrogram": "Analyzing audio spectrogram...",
    "llm_text": "Analyzing text with AI...",
    "community_forensics": "Running Community Forensics ViT...",
    "npr_detector": "Running NPR ViT detector...",
    "siglip_detector": "Running SigLIP detector...",
}


@shared_task
def dispatch_analysis(submission_id):
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        logger.error("Submission %s not found for analysis dispatch", submission_id)
        return

    configs = AnalyzerConfig.objects.filter(is_active=True)
    if not configs.exists():
        logger.warning("No active analyzers configured")
        submission.status = Submission.Status.COMPLETED
        submission.final_verdict = "inconclusive"
        submission.final_score = 0.5
        submission.save(update_fields=["status", "final_verdict", "final_score"])
        return

    submission.status_message = "Starting analyzers..."
    submission.save(update_fields=["status_message"])
    _publish_status(submission_id, "Starting analyzers...")

    tasks = []
    for config in configs:
        sig = run_analyzer.s(submission_id, config.id).set(
            queue=config.queue,
            soft_time_limit=config.timeout,
            time_limit=config.timeout + 30,
        )
        tasks.append(sig)

    callback = aggregate_verdicts.s(submission_id)
    chord(group(tasks))(callback)


@shared_task(bind=True, max_retries=1, soft_time_limit=120, time_limit=150)
def run_analyzer(self, submission_id, config_id):
    start_time = time.time()

    try:
        submission = Submission.objects.get(id=submission_id)
        config = AnalyzerConfig.objects.get(id=config_id)
    except (Submission.DoesNotExist, AnalyzerConfig.DoesNotExist) as e:
        logger.error("Missing submission or config: %s", e)
        return None

    try:
        analyzer_cls = load_analyzer_class(config.analyzer_class)
        analyzer = analyzer_cls()

        mime_supported = analyzer.supported_mime_types()
        if submission.mime_type not in mime_supported:
            logger.info(
                "Analyzer %s does not support %s, skipping", config.name, submission.mime_type
            )
            return None

        status_msg = ANALYZER_STATUS_MESSAGES.get(config.name, f"Running {config.name}...")
        submission.status_message = status_msg
        submission.save(update_fields=["status_message"])
        _publish_status(submission_id, status_msg, event="analyzer_start", analyzer=config.name)

        meta = dict(submission.metadata or {})
        meta["submission_id"] = str(submission_id)
        with local_file(submission.file) as path:
            output = analyzer.analyze(path, meta)
        execution_time = time.time() - start_time

        result = AnalysisResult.objects.create(
            submission=submission,
            analyzer=config,
            confidence=output.confidence,
            verdict=output.verdict,
            evidence=output.evidence,
            execution_time=execution_time,
        )
        _publish_status(submission_id, event="analyzer_done", analyzer=config.name, verdict=output.verdict)
        return str(result.id)

    except Exception as exc:
        execution_time = time.time() - start_time
        logger.exception("Analyzer %s failed on submission %s", config.name, submission_id)

        AnalysisResult.objects.create(
            submission=submission,
            analyzer=config,
            confidence=0.0,
            verdict=AnalysisResult.Verdict.ERROR,
            evidence={},
            execution_time=execution_time,
            error_message=str(exc),
        )
        _publish_status(submission_id, event="analyzer_done", analyzer=config.name, verdict="error")
        return None


@shared_task
def aggregate_verdicts(result_ids, submission_id):
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        logger.error("Submission %s not found for aggregation", submission_id)
        return

    submission.status_message = "Aggregating results..."
    submission.save(update_fields=["status_message"])
    _publish_status(submission_id, "Aggregating results...")

    results = list(submission.analysis_results.select_related("analyzer").all())

    if not results:
        submission.final_score = 0.5
        submission.final_verdict = "inconclusive"
    else:
        score, verdict = aggregate(results)
        submission.final_score = score
        submission.final_verdict = verdict

    submission.status = Submission.Status.COMPLETED
    submission.status_message = ""
    submission.save(update_fields=["final_score", "final_verdict", "status", "status_message"])
    _publish_status(
        submission_id, "",
        status="completed",
        final_score=float(submission.final_score),
        final_verdict=submission.final_verdict,
    )
    logger.info(
        "Submission %s completed: score=%.4f verdict=%s",
        submission_id, submission.final_score, submission.final_verdict,
    )

    from provenance.tasks import run_provenance_check
    run_provenance_check.delay(submission_id)


@shared_task(name="analyzers.tasks.rescue_stuck_submissions")
def rescue_stuck_submissions():
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(minutes=10)
    stuck = Submission.objects.filter(status=Submission.Status.PROCESSING, updated_at__lt=cutoff)
    count = stuck.count()
    if count:
        logger.warning("Rescuing %d stuck submissions", count)
        for sub in stuck:
            aggregate_verdicts.delay([], str(sub.id))
    return count


@shared_task(name="analyzers.tasks.run_weekly_retrain", soft_time_limit=3600, time_limit=3900)
def run_weekly_retrain(media_type: str = "image", triggered_by_id=None, min_samples_override=None):
    from datetime import timedelta
    from django.conf import settings
    from django.core.management import call_command
    from django.utils import timezone
    from io import StringIO

    from content.models import Submission
    from .models import RetrainRun

    if min_samples_override is not None:
        min_samples = int(min_samples_override)
    else:
        min_samples = getattr(settings, "RETRAIN_MIN_NEW_SAMPLES", 50)
    media_types_map = {
        "image": ["image/jpeg", "image/png", "image/webp"],
        "video": ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"],
        "audio": ["audio/mpeg", "audio/wav", "audio/ogg", "audio/flac"],
    }
    mimes = media_types_map.get(media_type, media_types_map["image"])

    last_success = (
        RetrainRun.objects.filter(media_type=media_type, status=RetrainRun.Status.SUCCESS)
        .order_by("-finished_at")
        .first()
    )
    since = last_success.finished_at if last_success and last_success.finished_at else timezone.now() - timedelta(days=365)

    qs = Submission.objects.filter(
        approved_for_training=True,
        verified_label__in=["real", "fake"],
        mime_type__in=mimes,
        status="completed",
        created_at__gte=since,
    )
    samples = qs.count()

    run = RetrainRun.objects.create(
        media_type=media_type,
        samples_used=samples,
        status=RetrainRun.Status.STARTED,
        triggered_by_id=triggered_by_id,
    )

    if samples < min_samples:
        run.status = RetrainRun.Status.SKIPPED
        run.error = f"only {samples} new approved samples, need {min_samples}"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])
        logger.info("retrain skipped: %s", run.error)
        _notify_retrain(run)
        _email_retrain(run)
        return str(run.id)

    buf = StringIO()
    try:
        call_command("retrain_detector", media_type=media_type, epochs=run.epochs, stdout=buf)
        run.hf_revision = buf.getvalue().splitlines()[-1][:120] if buf.getvalue() else ""
        run.status = RetrainRun.Status.SUCCESS
    except SoftTimeLimitExceeded:
        run.status = RetrainRun.Status.FAILED
        run.error = "soft time limit exceeded (worker likely OOM or training >1h)"
        logger.warning("retrain soft time limit")
    except Exception as exc:
        run.status = RetrainRun.Status.FAILED
        run.error = str(exc)[:2000]
        logger.exception("retrain failed")

    run.finished_at = timezone.now()
    run.save(update_fields=["hf_revision", "status", "error", "finished_at"])
    _notify_retrain(run)
    _email_retrain(run)
    return str(run.id)


def _notify_retrain(run):
    from django.conf import settings
    import requests

    url = getattr(settings, "DISCORD_WEBHOOK_URL", "")
    if not url:
        return
    color = {"success": 5763719, "skipped": 16776960, "failed": 15548997}.get(run.status, 8421504)
    payload = {
        "embeds": [{
            "title": f"Retrain {run.status}: {run.media_type}",
            "color": color,
            "fields": [
                {"name": "Samples", "value": str(run.samples_used), "inline": True},
                {"name": "HF rev", "value": run.hf_revision or "-", "inline": True},
                {"name": "Error", "value": (run.error or "-")[:1000], "inline": False},
            ],
        }],
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as exc:
        logger.warning("retrain notify failed: %s", exc)


def _email_retrain(run):
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives

    user = run.triggered_by
    if not user or not user.email:
        return
    status = run.status
    subject = f"[ProofLayer] Retrain {status}: {run.media_type}"
    lines = [
        f"Retrain run {run.id} finished with status: {status}.",
        f"Media type: {run.media_type}",
        f"Samples used: {run.samples_used}",
    ]
    if run.hf_revision:
        lines.append(f"HF revision: {run.hf_revision}")
    if run.error:
        lines.append(f"Error: {run.error}")
    text_body = "\n".join(lines)
    html_body = "<p>" + "</p><p>".join(lines) + "</p>"
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=True)
    except Exception as exc:
        logger.warning("retrain email failed: %s", exc)
