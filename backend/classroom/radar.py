from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median, pstdev

import numpy as np

from analyzers.models import AnalysisResult
from content.models import Submission
from plagiarism.models import SentenceVector

ALIGN_SIMILARITY = 0.88
MIN_SENTENCES = 4
MIN_SHARE = 0.35
STRONG_SHARE = 0.5
MIN_IN_ORDER = 0.6
OUTLIER_Z = 2.5
MIN_PAIRS_FOR_STATS = 6
MAX_SUBMISSIONS = 200
READABILITY_JUMP = 3.0
AI_JUMP_HIGH = 0.75
AI_JUMP_BASE = 0.3
MIN_HISTORY = 3
MIN_CLASS_WORKS = 5
MIN_CLASS_STUDENTS = 4


@dataclass
class Doc:
    submission_id: str
    student_id: int
    student: str
    vectors: np.ndarray


def alignment(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    sims = a @ b.T
    best_ab, best_ba = sims.max(axis=1), sims.max(axis=0)
    share = (float((best_ab >= ALIGN_SIMILARITY).mean()) + float((best_ba >= ALIGN_SIMILARITY).mean())) / 2
    targets = [int(j) for i, j in enumerate(sims.argmax(axis=1)) if best_ab[i] >= ALIGN_SIMILARITY]
    if len(targets) < 2:
        return share, 0.0
    in_order = sum(1 for x, y in zip(targets, targets[1:]) if y >= x) / (len(targets) - 1)
    return share, in_order


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
                "a": {"submission_id": a.submission_id, "student": a.student},
                "b": {"submission_id": b.submission_id, "student": b.student},
                "aligned_share": round(share, 3),
                "in_order": round(in_order, 3),
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


def level_jumps(history: dict[int, list[dict]]) -> list[dict]:
    jumps = []
    for rows in history.values():
        rows = sorted(rows, key=lambda r: r["created_at"])
        for k, row in enumerate(rows):
            prior = rows[:k]
            if len(prior) < MIN_HISTORY:
                continue
            reasons = []
            grades = [r["readability_grade"] for r in prior if r.get("readability_grade") is not None]
            if row.get("readability_grade") is not None and grades and row["readability_grade"] - median(grades) >= READABILITY_JUMP:
                reasons.append(f"reads at grade {row['readability_grade']:.0f}, earlier work at about {median(grades):.0f}")
            probs = [r["ai_probability"] for r in prior if r.get("ai_probability") is not None]
            if row.get("ai_probability") is not None and probs and row["ai_probability"] >= AI_JUMP_HIGH and median(probs) <= AI_JUMP_BASE:
                reasons.append("machine-writing score jumped from this student's usual range")
            if row.get("style_flag"):
                reasons.append("style differs sharply from this student's earlier work")
            if reasons:
                jumps.append({
                    "submission_id": row["submission_id"],
                    "student": row["student"],
                    "created_at": row["created_at"].isoformat(),
                    "reasons": reasons,
                })
    return sorted(jumps, key=lambda j: j["created_at"], reverse=True)


def _docs(submissions: list[Submission]) -> list[Doc]:
    by_submission = defaultdict(list)
    rows = (
        SentenceVector.objects.filter(submission__in=submissions)
        .order_by("submission_id", "position")
        .values_list("submission_id", "embedding")
    )
    for submission_id, embedding in rows:
        by_submission[submission_id].append(np.asarray(embedding, dtype=np.float32))
    docs = []
    for s in submissions:
        vectors = by_submission.get(s.id, [])
        if len(vectors) >= MIN_SENTENCES:
            docs.append(Doc(str(s.id), s.user_id, s.user.username, np.vstack(vectors)))
    return docs


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
            evidence[submission_id]["readability_grade"] = ev.get("readability_grade")
        elif name == "text_style":
            evidence[submission_id]["style_flag"] = verdict == AnalysisResult.Verdict.SUSPICIOUS
    history = defaultdict(list)
    for s in submissions:
        if s.id in evidence:
            history[s.user_id].append({
                "submission_id": str(s.id),
                "student": s.user.username,
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
    docs = _docs(submissions)
    students = len({d.student_id for d in docs})
    enough = len(docs) >= MIN_CLASS_WORKS and students >= MIN_CLASS_STUDENTS
    pairs = shared_skeletons(docs) if enough else []
    return {
        "submissions": len(submissions),
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
        "level_jumps": level_jumps(_history(submissions)),
    }
