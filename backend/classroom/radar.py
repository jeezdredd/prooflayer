from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean, median, pstdev

import numpy as np

from analyzers.models import AnalysisResult
from common.names import display_name
from content.models import Submission
from plagiarism.models import SentenceVector, TextFingerprint

from .attention import cleared_q
from .models import Membership
from .serializers import supervisor_ids

ALIGN_SIMILARITY = 0.92
MIN_SENTENCES = 4
MIN_SHARE = 0.6
STRONG_SHARE = 0.7
MIN_IN_ORDER = 0.6
OUTLIER_Z = 2.5
MIN_PAIRS_FOR_STATS = 6
MAX_SUBMISSIONS = 200
AI_JUMP_HIGH = 0.75
AI_JUMP_BASE = 0.3
MIN_HISTORY = 3
MIN_CLASS_WORKS = 5
MIN_CLASS_STUDENTS = 4
MAX_EXAMPLES = 3
EXAMPLE_CHARS = 320
JUMP_WORDS = 5


@dataclass
class Doc:
    submission_id: str
    student_id: int
    student: str
    vectors: np.ndarray
    filename: str = ""
    created_at: str = ""
    unattributed: bool = False
    spans: list[tuple[int, int]] = field(default_factory=list)
    sentences: list[str] = field(default_factory=list)


def alignment(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    sims = a @ b.T
    best_ab, best_ba = sims.max(axis=1), sims.max(axis=0)
    share = (float((best_ab >= ALIGN_SIMILARITY).mean()) + float((best_ba >= ALIGN_SIMILARITY).mean())) / 2
    targets = [int(j) for i, j in enumerate(sims.argmax(axis=1)) if best_ab[i] >= ALIGN_SIMILARITY]
    if len(targets) < 2:
        return share, 0.0
    in_order = sum(1 for x, y in zip(targets, targets[1:]) if y >= x) / (len(targets) - 1)
    return share, in_order


def matched_sentences(a: np.ndarray, b: np.ndarray) -> int:
    return int(((a @ b.T).max(axis=1) >= ALIGN_SIMILARITY).sum())


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= EXAMPLE_CHARS else text[: EXAMPLE_CHARS - 3].rstrip() + "..."


def examples(a: Doc, b: Doc, limit: int = MAX_EXAMPLES) -> list[dict]:
    if len(a.sentences) != len(a.vectors) or len(b.sentences) != len(b.vectors):
        return []
    sims = a.vectors @ b.vectors.T
    best = sims.argmax(axis=1)
    found = sorted(
        ((float(sims[i, j]), i, int(j)) for i, j in enumerate(best) if sims[i, j] >= ALIGN_SIMILARITY),
        reverse=True,
    )[:limit]
    return [
        {"a": _clip(a.sentences[i]), "b": _clip(b.sentences[j])}
        for _, i, j in sorted(found, key=lambda item: item[1])
        if a.sentences[i].strip() and b.sentences[j].strip()
    ]


def _ref(doc: Doc) -> dict:
    return {
        "submission_id": doc.submission_id,
        "student": doc.student,
        "filename": doc.filename,
        "created_at": doc.created_at,
        "unattributed": doc.unattributed,
    }


def shared_skeletons(docs: list[Doc]) -> list[dict]:
    scored = []
    for i, a in enumerate(docs):
        for b in docs[i + 1 :]:
            if a.student_id == b.student_id:
                continue
            share, in_order = alignment(a.vectors, b.vectors)
            scored.append((a, b, share, in_order))
    if not scored:
        return []
    shares = [s for _, _, s, _ in scored]
    if len(shares) >= MIN_PAIRS_FOR_STATS:
        bar = max(MIN_SHARE, mean(shares) + OUTLIER_Z * pstdev(shares))
    else:
        bar = STRONG_SHARE
    pairs = []
    for a, b, share, in_order in scored:
        if share >= bar and in_order >= MIN_IN_ORDER:
            pairs.append({
                "a": _ref(a),
                "b": _ref(b),
                "aligned_share": round(share, 3),
                "in_order": round(in_order, 3),
                "a_sentences": len(a.vectors),
                "a_matched": matched_sentences(a.vectors, b.vectors),
                "b_sentences": len(b.vectors),
                "b_matched": matched_sentences(b.vectors, a.vectors),
                "examples": examples(a, b),
            })
    return sorted(pairs, key=lambda p: -p["aligned_share"])


def clusters(pairs: list[dict]) -> list[list[str]]:
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in pairs:
        ra, rb = find(p["a"]["submission_id"]), find(p["b"]["submission_id"])
        if ra != rb:
            parent[ra] = rb
    groups = defaultdict(list)
    for node in list(parent):
        groups[find(node)].append(node)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=len, reverse=True)


def _number(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def level_jumps(history: dict[int, list[dict]]) -> list[dict]:
    jumps = []
    for rows in history.values():
        rows = sorted(rows, key=lambda r: r["created_at"])
        for k, row in enumerate(rows):
            prior = rows[:k]
            reasons = []
            if row.get("grade_flag"):
                reason = {"kind": "vocabulary", "words": list(row.get("words") or [])[:JUMP_WORDS]}
                now = _number(row.get("words_per_sentence"))
                before = [v for v in (_number(r.get("words_per_sentence")) for r in prior) if v is not None]
                if now is not None and len(before) >= MIN_HISTORY:
                    reason["words_per_sentence"] = {"now": round(now, 1), "before": round(median(before), 1)}
                reasons.append(reason)
            probs = [r["ai_probability"] for r in prior if _number(r.get("ai_probability")) is not None]
            current = _number(row.get("ai_probability"))
            enough = current is not None and len(probs) >= MIN_HISTORY
            if enough and current >= AI_JUMP_HIGH and median(probs) <= AI_JUMP_BASE:
                reasons.append({"kind": "ai"})
            if row.get("style_flag"):
                reasons.append({"kind": "style"})
            if reasons:
                jumps.append({
                    "submission_id": row["submission_id"],
                    "student": row["student"],
                    "filename": row["filename"],
                    "created_at": row["created_at"].isoformat(),
                    "reasons": reasons,
                })
    return sorted(jumps, key=lambda j: j["created_at"], reverse=True)


def _docs(submissions: list[Submission], unattributed: set) -> list[Doc]:
    by_submission = defaultdict(list)
    spans = defaultdict(list)
    rows = (
        SentenceVector.objects.filter(submission__in=submissions)
        .order_by("submission_id", "position")
        .values_list("submission_id", "embedding", "start", "end")
    )
    for submission_id, embedding, start, end in rows:
        by_submission[submission_id].append(np.asarray(embedding, dtype=np.float32))
        spans[submission_id].append((start, end))
    docs = []
    for s in submissions:
        vectors = by_submission.get(s.id, [])
        if len(vectors) < MIN_SENTENCES:
            continue
        loose = s.id in unattributed
        docs.append(Doc(
            submission_id=str(s.id),
            student_id=-len(docs) - 1 if loose else s.user_id,
            student="" if loose else display_name(s.user),
            vectors=np.vstack(vectors),
            filename=s.original_filename,
            created_at=s.created_at.isoformat(),
            unattributed=loose,
            spans=spans[s.id],
        ))
    return docs


def _load_sentences(pairs: list[dict], docs: list[Doc]) -> None:
    wanted = {p["a"]["submission_id"] for p in pairs} | {p["b"]["submission_id"] for p in pairs}
    by_id = {d.submission_id: d for d in docs if d.submission_id in wanted}
    texts = TextFingerprint.objects.filter(submission_id__in=list(by_id)).values_list("submission_id", "text")
    for submission_id, text in texts:
        doc = by_id[str(submission_id)]
        doc.sentences = [text[start:end] for start, end in doc.spans]
    for p in pairs:
        p["examples"] = examples(by_id[p["a"]["submission_id"]], by_id[p["b"]["submission_id"]])


def _history(submissions: list[Submission]) -> dict[int, list[dict]]:
    evidence = defaultdict(dict)
    results = AnalysisResult.objects.filter(
        submission__in=submissions, analyzer__name__in=("text_classifier", "text_grade_fit", "text_style"),
    ).values_list("submission_id", "analyzer__name", "verdict", "evidence")
    for submission_id, name, verdict, ev in results:
        ev = ev if isinstance(ev, dict) else {}
        if name == "text_classifier":
            evidence[submission_id]["ai_probability"] = ev.get("ai_probability")
        elif name == "text_grade_fit":
            evidence[submission_id]["grade_flag"] = verdict == AnalysisResult.Verdict.SUSPICIOUS
            words = [w for w in ev.get("beyond_level_words") or [] if isinstance(w, str)]
            evidence[submission_id]["words"] = words[:JUMP_WORDS]
            evidence[submission_id]["words_per_sentence"] = ev.get("words_per_sentence")
        elif name == "text_style":
            evidence[submission_id]["style_flag"] = verdict == AnalysisResult.Verdict.SUSPICIOUS
    history = defaultdict(list)
    for s in submissions:
        if s.id in evidence:
            history[s.user_id].append({
                "submission_id": str(s.id),
                "student": display_name(s.user),
                "filename": s.original_filename,
                "created_at": s.created_at,
                **evidence[s.id],
            })
    return history


def class_radar(classroom, since) -> dict:
    submissions = list(
        Submission.objects.filter(classroom=classroom, status=Submission.Status.COMPLETED, created_at__gte=since)
        .select_related("user")
        .order_by("-created_at")[:MAX_SUBMISSIONS]
    )
    members = set(Membership.objects.filter(classroom=classroom).values_list("user_id", flat=True))
    supervisors = supervisor_ids(classroom)
    unattributed = {s.id for s in submissions if s.user_id not in members and s.user_id in supervisors}
    docs = _docs(submissions, unattributed)
    students = len({d.student_id for d in docs if not d.unattributed})
    enough = len(docs) >= MIN_CLASS_WORKS and students >= MIN_CLASS_STUDENTS
    pairs = shared_skeletons(docs) if enough else []
    if pairs:
        _load_sentences(pairs, docs)
    cleared = {
        str(pk) for pk in Submission.objects.filter(pk__in=[s.pk for s in submissions]).filter(cleared_q())
        .values_list("pk", flat=True)
    }
    attributed = [s for s in submissions if s.id not in unattributed]
    jumps = [j for j in level_jumps(_history(attributed)) if j["submission_id"] not in cleared]
    return {
        "submissions": len(submissions),
        "compared": len(docs),
        "level": classroom.level,
        "skeleton_data": {
            "enough": enough,
            "works": len(docs),
            "need_works": MIN_CLASS_WORKS,
            "students": students,
            "need_students": MIN_CLASS_STUDENTS,
        },
        "jump_history_needed": MIN_HISTORY,
        "shared_skeletons": pairs,
        "clusters": clusters(pairs),
        "level_jumps": jumps,
    }
