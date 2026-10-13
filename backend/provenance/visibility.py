import uuid

from common.age import can_view_sensitive
from content.models import Submission


def matched_submission_id(result):
    if not isinstance(result.raw_data, dict):
        return None
    value = result.raw_data.get("submission_id")
    try:
        return str(uuid.UUID(str(value))) if value else None
    except ValueError:
        return None


def sensitive_match_ids(results) -> set[str]:
    matched_ids = {mid for mid in map(matched_submission_id, results) if mid}
    if not matched_ids:
        return set()
    return {
        str(sid)
        for sid in Submission.objects.filter(id__in=matched_ids, is_sensitive=True).values_list("id", flat=True)
    }


def results_for_viewer(results, user, sensitive_ids: set[str]) -> list:
    if can_view_sensitive(user):
        return list(results)
    return [r for r in results if matched_submission_id(r) not in sensitive_ids]
