import logging

from celery import shared_task
from django.core.cache import cache

from factcheck.ner import _regex_split, extract_claim_sentences, extract_entities
from factcheck.services import (
    _build_assessed_claims,
    check_google_fact_check,
    format_search_context,
    lookup_wikipedia,
    match_wiki,
    search_web,
)

logger = logging.getLogger(__name__)

STAGE_TTL = 600


def _set_stage(task_id, stage, progress, result=None, error=None):
    payload = {"stage": stage, "progress": progress}
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    cache.set(f"fc:{task_id}", payload, timeout=STAGE_TTL)


@shared_task(bind=True, soft_time_limit=300, time_limit=330)
def run_factcheck(self, text):
    task_id = self.request.id
    try:
        _set_stage(task_id, "extracting", 10)
        claims_raw = extract_claim_sentences(text, max_claims=8)
        if len(claims_raw) < 2:
            regex_claims = _regex_split(text, 8)
            for rc in regex_claims:
                if rc not in claims_raw:
                    claims_raw.append(rc)
            claims_raw = claims_raw[:8]
        entities = extract_entities(text)

        _set_stage(task_id, "searching", 30)
        search_query = " ".join(claims_raw[:2])[:200]
        web_results = search_web(search_query)
        wiki_hits = []
        for c in claims_raw[:4]:
            hit = lookup_wikipedia(c[:120])
            if hit:
                wiki_hits.append(hit)
        context = format_search_context(web_results, wiki_hits)

        _set_stage(task_id, "assessing", 55)
        raw_assessed = _build_assessed_claims(claims_raw, context)
        seen_texts: set = set()
        merged = []
        for i, item in enumerate(raw_assessed):
            claim_text = item.get("claim", "").strip() or (claims_raw[i] if i < len(claims_raw) else "")
            if not claim_text or claim_text in seen_texts:
                continue
            seen_texts.add(claim_text)
            merged.append({**item, "claim": claim_text})
        for original in claims_raw:
            if original and original not in seen_texts:
                seen_texts.add(original)
                merged.append({
                    "claim": original,
                    "assessment": "uncertain",
                    "confidence": 0,
                    "explanation": "Could not assess.",
                })
        claims = merged

        _set_stage(task_id, "cross_referencing", 80)
        top_sources = [
            {"title": r.get("title", ""), "url": r.get("url", "")}
            for r in web_results[:3]
            if r.get("url")
        ]
        enriched = []
        for claim_obj in claims:
            ctext = claim_obj.get("claim", "")
            fact_checks = check_google_fact_check(ctext)
            wiki = match_wiki(ctext, wiki_hits)
            enriched.append({
                **claim_obj,
                "fact_checks": fact_checks,
                "sources": top_sources,
                "wikipedia": wiki,
            })

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
