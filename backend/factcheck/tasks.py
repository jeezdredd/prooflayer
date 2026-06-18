import logging

from celery import shared_task
from django.core.cache import cache

from factcheck.ner import extract_claim_sentences, extract_entities
from factcheck.services import _build_assessed_claims, check_google_fact_check, search_web

logger = logging.getLogger(__name__)

STAGE_TTL = 600


def _set_stage(task_id, stage, progress, result=None, error=None):
    payload = {"stage": stage, "progress": progress}
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    cache.set(f"fc:{task_id}", payload, timeout=STAGE_TTL)


@shared_task(bind=True, soft_time_limit=240, time_limit=270)
def run_factcheck(self, text):
    task_id = self.request.id
    try:
        _set_stage(task_id, "extracting", 10)
        claims_raw = extract_claim_sentences(text, max_claims=8)
        entities = extract_entities(text)

        _set_stage(task_id, "searching", 30)
        search_query = " ".join(claims_raw[:2])[:200]
        search_context = search_web(search_query)

        _set_stage(task_id, "assessing", 55)
        claims = _build_assessed_claims(claims_raw, search_context)
        seen_claims: set = set()
        claims = [c for c in claims if not (c.get("claim", "") in seen_claims or seen_claims.add(c.get("claim", "")))]

        _set_stage(task_id, "cross_referencing", 80)
        enriched = []
        for claim_obj in claims:
            fact_checks = check_google_fact_check(claim_obj.get("claim", ""))
            enriched.append({**claim_obj, "fact_checks": fact_checks})

        false_count = sum(1 for c in enriched if c.get("assessment") == "likely_false")
        uncertain_count = sum(1 for c in enriched if c.get("assessment") == "uncertain")
        total = len(enriched)

        if total == 0:
            overall = "no_claims"
        elif false_count / max(total, 1) >= 0.4:
            overall = "misleading"
        elif (false_count + uncertain_count) / max(total, 1) >= 0.5:
            overall = "mixed"
        else:
            overall = "mostly_accurate"

        result = {
            "claims_count": total,
            "overall_verdict": overall,
            "claims": enriched,
            "entities": entities,
        }
        _set_stage(task_id, "done", 100, result=result)
        return result

    except Exception as exc:
        logger.exception("Factcheck task %s failed", task_id)
        _set_stage(task_id, "error", 0, error=str(exc))
        raise
