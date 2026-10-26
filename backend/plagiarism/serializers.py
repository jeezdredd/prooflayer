import math

from classroom.access import supervised_q, visible_submissions_q
from classroom.models import Classroom
from common.names import display_name
from content.models import Submission

from .academic import PAPER_ENGINES
from .models import TextFingerprint

EXCERPTS = 5
EXCERPT_CHARS = 300


def _clip(chunk: str) -> str:
    chunk = " ".join(chunk.split())
    return chunk if len(chunk) <= EXCERPT_CHARS else chunk[:EXCERPT_CHARS].rstrip() + "…"


def _cut(text: str | None, span) -> str:
    if not text or not span:
        return ""
    return _clip(text[span[0]:span[1]])


def _evidence(match: dict, own_text: str, source_text: str | None) -> tuple[list[str], list[str], list[str]]:
    pairs = match.get("pairs") or [{"own": span} for span in match["spans"]]
    longest = sorted(pairs, key=lambda p: p["own"][0] - p["own"][1])[:EXCERPTS]
    chosen = sorted(longest, key=lambda p: p["own"][0])
    own = [_cut(own_text, p["own"]) for p in chosen]
    if match["source"] == "web":
        source = [_clip(p.get("text", "")) for p in chosen]
    else:
        source = [_cut(source_text, p.get("src")) for p in chosen]
    kinds = [p.get("kind", match["kind"]) for p in chosen]
    return own, source, kinds


def _share(matched: int, report) -> float:
    headline = 100 - math.floor((report.originality or 0) + 0.5)
    return max(0.0, min(round(100 * matched / max(1, report.total_chars), 1), float(headline)))


def main_source(report, classroom_id=None) -> dict | None:
    if report is None or report.status != report.Status.DONE or not report.matches:
        return None
    top = report.matches[0]
    share = round(100 * top.get("matched_chars", 0) / max(1, report.total_chars), 1)
    if top.get("source") == "web":
        return {"source": "web", "title": top.get("title", ""), "url": top.get("url", ""), "share": share}
    author = None
    if classroom_id is not None and top.get("submission_id"):
        source = Submission.objects.filter(id=top["submission_id"], classroom_id=classroom_id).select_related("user").first()
        if source is not None:
            author = display_name(source.user)
    return {"source": "internal", "author": author, "share": share}


def _hidden_reason(submission, user) -> str:
    if user is None or not getattr(user, "is_authenticated", False) or submission.user_id != user.id:
        return "other_class"
    if Classroom.objects.filter(supervised_q(user)).exists():
        return "other_class"
    return "student_view"


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
        "web_status": report.web_status or ("ok" if report.web_searched else "off"),
        "web_engines": report.web_engines or [],
        "web_queries": report.web_queries,
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
    texts = {}
    if visible:
        rows = TextFingerprint.objects.filter(submission_id__in=list(visible)).values_list("submission_id", "text")
        texts = {str(k): v for k, v in rows}
    hidden_reason = None
    for match in report.matches:
        matched = match.get("matched_chars", 0)
        source = visible.get(match.get("submission_id"))
        excerpts, source_excerpts, excerpt_kinds = _evidence(match, own_text, texts.get(match.get("submission_id")))
        row = {
            "source": match["source"],
            "kind": match["kind"],
            "kinds": match.get("kinds") or [match["kind"]],
            "matched_chars": matched,
            "share": _share(matched, report),
            "spans": match["spans"],
            "excerpts": excerpts,
            "source_excerpts": source_excerpts,
            "excerpt_kinds": excerpt_kinds,
            "similarity": match.get("similarity"),
            "hidden": False,
        }
        if match["source"] == "web":
            row.update({"url": match["url"], "title": match.get("title", ""), "engine": match.get("engine")})
            if match.get("engine") in PAPER_ENGINES:
                row.update({
                    "authors": match.get("authors") or [],
                    "authors_total": match.get("authors_total") or len(match.get("authors") or []),
                    "year": match.get("year"),
                    "venue": match.get("venue") or "",
                })
        else:
            row["submitted_at"] = match.get("submitted_at")
            if source is not None:
                row.update({
                    "submission_id": str(source.id),
                    "title": source.original_filename,
                    "author": display_name(source.user),
                    "classroom": source.classroom.name if source.classroom else None,
                })
            else:
                if hidden_reason is None:
                    hidden_reason = _hidden_reason(submission, user)
                row.update({"title": None, "hidden": True, "hidden_reason": hidden_reason})
        payload["matches"].append(row)
    return payload
