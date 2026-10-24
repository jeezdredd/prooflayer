import logging

from celery import shared_task

from .models import ShadowSet
from .shadow import build

logger = logging.getLogger(__name__)

LLM_FAILED = "llm_failed"
NO_ANSWERS = "no_answers"


@shared_task(bind=True, soft_time_limit=3600, time_limit=3660)
def build_shadow_set(self, shadow_id: str):
    shadow = ShadowSet.objects.filter(id=shadow_id).first()
    if shadow is None:
        return None
    shadow.status = ShadowSet.Status.RUNNING
    shadow.save(update_fields=["status"])
    try:
        written = build(shadow)
    except Exception:
        logger.exception("shadow set %s failed", shadow_id)
        shadow.status, shadow.error = ShadowSet.Status.FAILED, LLM_FAILED
        shadow.save(update_fields=["status", "error"])
        return None
    shadow.status = ShadowSet.Status.DONE if written else ShadowSet.Status.FAILED
    shadow.error = "" if written else NO_ANSWERS
    shadow.save(update_fields=["status", "error"])
    return written
