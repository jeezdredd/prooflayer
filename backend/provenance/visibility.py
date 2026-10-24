import uuid

from classroom.access import visible_submissions_q
from common.age import can_view_sensitive
from common.names import display_name
from content.models import Submission

from .models import ProvenanceResult

INTERNAL_SOURCES = (ProvenanceResult.SourceType.PHASH_MATCH, ProvenanceResult.SourceType.CLIP_NEIGHBOUR)
SHOWN_EXTERNAL_SOURCES = (ProvenanceResult.SourceType.TINEYE, ProvenanceResult.SourceType.GOOGLE_VISION)
SAME_PICTURE_MAX_DISTANCE = 4
SOURCE_ORDER = {ProvenanceResult.SourceType.PHASH_MATCH: 0, ProvenanceResult.SourceType.CLIP_NEIGHBOUR: 1}


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


def _internal_links(submission) -> list[tuple]:
    own = [
        (r, matched_submission_id(r))
        for r in submission.provenance_results.filter(source_type__in=INTERNAL_SOURCES)
    ]
    reverse = [
        (r, str(r.submission_id))
        for r in ProvenanceResult.objects.filter(
            source_type__in=INTERNAL_SOURCES, raw_data__submission_id=str(submission.id),
        ).exclude(submission_id=submission.id)
    ]
    links = sorted(
        (link for link in own + reverse if link[1]),
        key=lambda link: (SOURCE_ORDER[link[0].source_type], -(link[0].similarity_score or 0)),
    )
    seen = set()
    unique = []
    for result, matched_id in links:
        if matched_id in seen:
            continue
        seen.add(matched_id)
        unique.append((result, matched_id))
    return unique


def _visible_ids(viewer, matched_ids: set[str]) -> set[str]:
    if viewer is None or not getattr(viewer, "is_authenticated", False) or not matched_ids:
        return set()
    queryset = Submission.objects.filter(id__in=matched_ids)
    if not viewer.is_staff:
        queryset = queryset.filter(visible_submissions_q(viewer))
    return {str(sid) for sid in queryset.values_list("id", flat=True)}


def _kind(result) -> str:
    if result.source_type == ProvenanceResult.SourceType.CLIP_NEIGHBOUR:
        return "similar"
    distance = result.raw_data.get("distance") if isinstance(result.raw_data, dict) else None
    return "same" if isinstance(distance, (int, float)) and distance <= SAME_PICTURE_MAX_DISTANCE else "near"


def _scope(submission, other, viewer, visible: bool) -> str:
    if visible:
        mine = viewer is not None and getattr(viewer, "is_authenticated", False) and other.user_id == viewer.id
        return "yours" if mine else "visible"
    if submission.classroom_id and other.classroom_id == submission.classroom_id:
        return "same_class"
    school = submission.classroom.organization_id if submission.classroom_id else None
    if school and other.classroom_id and other.classroom.organization_id == school:
        return "same_school"
    return "elsewhere"


def _internal_row(result, submission, other, viewer, visible: bool) -> dict:
    return {
        "id": str(result.id),
        "source_type": result.source_type,
        "source_url": "",
        "title": other.original_filename if visible else "",
        "similarity_score": result.similarity_score,
        "found_at": result.found_at,
        "is_sensitive": other.is_sensitive,
        "raw_data": {},
        "match": {
            "kind": _kind(result),
            "scope": _scope(submission, other, viewer, visible),
            "submission_id": str(other.id) if visible else None,
            "author": display_name(other.user) if visible else None,
            "classroom": other.classroom.name if visible and other.classroom_id else None,
            "submitted_at": other.created_at.isoformat() if visible else None,
        },
    }


def _external_row(result) -> dict:
    return {
        "id": str(result.id),
        "source_type": result.source_type,
        "source_url": result.source_url,
        "title": result.title,
        "similarity_score": result.similarity_score,
        "found_at": result.found_at,
        "is_sensitive": False,
        "raw_data": {},
        "match": None,
    }


def provenance_rows(submission, viewer) -> list[dict]:
    links = _internal_links(submission)
    matched_ids = {matched_id for _, matched_id in links}
    matched = {
        str(s.id): s
        for s in Submission.objects.filter(id__in=matched_ids).select_related("user", "classroom")
    }
    visible = _visible_ids(viewer, matched_ids)
    sensitive_ok = can_view_sensitive(viewer)
    rows = []
    for result, matched_id in links:
        other = matched.get(matched_id)
        if other is None or (other.is_sensitive and not sensitive_ok):
            continue
        rows.append(_internal_row(result, submission, other, viewer, matched_id in visible))
    rows.extend(
        _external_row(r) for r in submission.provenance_results.filter(source_type__in=SHOWN_EXTERNAL_SOURCES)
    )
    return rows
