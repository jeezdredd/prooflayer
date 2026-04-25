import logging
import time

from celery import chord, group, shared_task

from content.models import Submission

from .aggregator import aggregate
from .models import AnalyzerConfig, AnalysisResult
from .registry import load_analyzer_class

logger = logging.getLogger(__name__)


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

        output = analyzer.analyze(submission.file.path, submission.metadata)
        execution_time = time.time() - start_time

        result = AnalysisResult.objects.create(
            submission=submission,
            analyzer=config,
            confidence=output.confidence,
            verdict=output.verdict,
            evidence=output.evidence,
            execution_time=execution_time,
        )
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
        return None


@shared_task
def aggregate_verdicts(result_ids, submission_id):
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        logger.error("Submission %s not found for aggregation", submission_id)
        return

    results = list(submission.analysis_results.select_related("analyzer").all())

    if not results:
        submission.final_score = 0.5
        submission.final_verdict = "inconclusive"
    else:
        score, verdict = aggregate(results)
        submission.final_score = score
        submission.final_verdict = verdict

    submission.status = Submission.Status.COMPLETED
    submission.save(update_fields=["final_score", "final_verdict", "status"])
    logger.info(
        "Submission %s completed: score=%.4f verdict=%s",
        submission_id, submission.final_score, submission.final_verdict,
    )

    from provenance.tasks import run_provenance_check
    run_provenance_check.delay(submission_id)
