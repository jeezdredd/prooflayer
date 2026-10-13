from classroom.access import visible_submissions_q
from content.models import Submission

EXCERPTS = 5
EXCERPT_CHARS = 300


def _excerpts(text: str, spans) -> list[str]:
    out = []
    for start, end in spans[:EXCERPTS]:
        chunk = text[start:end]
        out.append(chunk if len(chunk) <= EXCERPT_CHARS else chunk[:EXCERPT_CHARS] + "…")
    return out


def report_payload(submission, user) -> dict | None:
    report = getattr(submission, "plagiarism_report", None)
    if report is None:
        return None
    payload = {
        "status": report.status,
        "originality": report.originality,
        "matched_chars": report.matched_chars,
        "total_chars": report.total_chars,
        "web_searched": report.web_searched,
        "checked_at": report.updated_at.isoformat(),
        "matches": [],
    }
    if report.status != report.Status.DONE:
        return payload
    fingerprint = getattr(submission, "text_fingerprint", None)
    own_text = fingerprint.text if fingerprint else ""
    internal_ids = [m["submission_id"] for m in report.matches if m.get("source") == "internal"]
    visible = {}
    if internal_ids and user is not None and user.is_authenticated:
        qs = Submission.objects.filter(id__in=internal_ids).select_related("user", "classroom")
        if not user.is_staff:
            qs = qs.filter(visible_submissions_q(user))
        visible = {str(s.id): s for s in qs}
    for match in report.matches:
        row = {
            "source": match["source"],
            "kind": match["kind"],
            "matched_chars": match.get("matched_chars", 0),
            "share": round(100 * match.get("matched_chars", 0) / max(1, report.total_chars), 1),
            "spans": match["spans"],
            "excerpts": _excerpts(own_text, match["spans"]),
            "similarity": match.get("similarity"),
        }
        if match["source"] == "web":
            row.update({"url": match["url"], "title": match.get("title", "")})
        else:
            source = visible.get(match["submission_id"])
            row["submitted_at"] = match.get("submitted_at")
            if source is not None:
                row.update({
                    "submission_id": str(source.id),
                    "title": source.original_filename,
                    "author": source.user.username,
                    "classroom": source.classroom.name if source.classroom else None,
                })
            else:
                row["title"] = "Another ProofLayer submission"
        payload["matches"].append(row)
    return payload
