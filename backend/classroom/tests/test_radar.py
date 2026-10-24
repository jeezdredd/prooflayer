from datetime import timedelta

import numpy as np
import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from analyzers.models import AnalysisResult
from analyzers.tests.factories import AnalysisResultFactory, AnalyzerConfigFactory
from billing.models import Subscription, get_or_create_subscription
from classroom.models import Classroom, Membership
from classroom.radar import Doc, alignment, clusters, examples, level_jumps, shared_skeletons
from content.models import Submission, VerdictObjection
from content.tests.factories import SubmissionFactory
from plagiarism.models import EMBED_DIM, SentenceVector, TextFingerprint
from users.tests.factories import UserFactory


def unit(seed: int, dim: int = 16) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=dim)
    return v / np.linalg.norm(v)


def doc(key: str, student: int, seeds: list[int]) -> Doc:
    return Doc(key, student, f"s{student}", np.vstack([unit(s) for s in seeds]))


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _teacher():
    user = UserFactory(is_verified=True)
    sub = get_or_create_subscription(user)
    sub.tier = Subscription.Tier.EDUCATION
    sub.save(update_fields=["tier"])
    return user


class TestAlignment:
    def test_same_sentences_in_order(self):
        share, in_order = alignment(doc("a", 1, [1, 2, 3, 4]).vectors, doc("b", 2, [1, 2, 3, 4]).vectors)
        assert share == 1.0 and in_order == 1.0

    def test_shuffled_sentences_lose_order(self):
        share, in_order = alignment(doc("a", 1, [1, 2, 3, 4]).vectors, doc("b", 2, [4, 3, 2, 1]).vectors)
        assert share == 1.0 and in_order == 0.0

    def test_unrelated_texts(self):
        share, _ = alignment(doc("a", 1, [1, 2, 3, 4]).vectors, doc("b", 2, [11, 12, 13, 14]).vectors)
        assert share == 0.0


class TestSkeletons:
    def test_outlier_pair_is_reported_and_clustered(self):
        docs = [doc(f"d{i}", i, [100 * i + k for k in range(5)]) for i in range(1, 5)]
        docs.append(doc("d0", 0, [0, 1, 2, 3, 99]))
        docs.append(doc("copy", 9, [0, 1, 2, 3, 4]))
        pairs = shared_skeletons(docs)
        assert [(p["a"]["submission_id"], p["b"]["submission_id"]) for p in pairs] == [("d0", "copy")]
        assert clusters(pairs) == [["copy", "d0"]]

    def test_same_student_is_never_paired(self):
        assert shared_skeletons([doc("a", 1, [1, 2, 3, 4]), doc("b", 1, [1, 2, 3, 4])]) == []

    def test_small_class_needs_a_strong_overlap(self):
        assert shared_skeletons([doc("a", 1, [1, 2, 3, 4]), doc("b", 2, [1, 7, 8, 9])]) == []
        assert len(shared_skeletons([doc("a", 1, [1, 2, 3, 4]), doc("b", 2, [1, 2, 3, 8])])) == 1

    def test_pair_says_how_many_sentences_match(self):
        pairs = shared_skeletons([doc("a", 1, [1, 2, 3, 4]), doc("b", 2, [1, 2, 3, 8])])
        assert pairs[0]["a_sentences"] == 4 and pairs[0]["a_matched"] == 3
        assert pairs[0]["b_sentences"] == 4 and pairs[0]["b_matched"] == 3
        assert pairs[0]["examples"] == []

    def test_examples_quote_the_matching_sentences_in_text_order(self):
        a = doc("a", 1, [1, 2, 3, 4])
        b = doc("b", 2, [9, 3, 1, 2])
        a.sentences = ["A one.", "A two.", "A three.", "A four."]
        b.sentences = ["B nine.", "B three.", "B one.", "B two."]
        assert examples(a, b) == [
            {"a": "A one.", "b": "B one."},
            {"a": "A two.", "b": "B two."},
            {"a": "A three.", "b": "B three."},
        ]

    def test_clusters_join_chains(self):
        pairs = [
            {"a": {"submission_id": "x"}, "b": {"submission_id": "y"}},
            {"a": {"submission_id": "y"}, "b": {"submission_id": "z"}},
            {"a": {"submission_id": "p"}, "b": {"submission_id": "q"}},
        ]
        assert clusters(pairs) == [["x", "y", "z"], ["p", "q"]]


class TestLevelJumps:
    def _row(self, day, **fields):
        return {"submission_id": f"w{day}", "student": "kid", "filename": f"w{day}.txt", "created_at": timezone.now() + timedelta(days=day), **fields}

    def test_vocabulary_flag_and_ai_jump(self):
        rows = [
            self._row(0, grade_flag=False, ai_probability=0.1),
            self._row(1, grade_flag=False, ai_probability=0.2),
            self._row(2, grade_flag=False, ai_probability=0.15),
            self._row(3, grade_flag=True, words=["идентичность", "цивилизация"], ai_probability=0.9),
        ]
        jumps = level_jumps({1: rows})
        assert len(jumps) == 1 and jumps[0]["submission_id"] == "w3"
        assert jumps[0]["reasons"] == [{"kind": "vocabulary", "words": ["идентичность", "цивилизация"]}, {"kind": "ai"}]
        assert jumps[0]["filename"] == "w3.txt"

    def test_vocabulary_follows_the_age_check_not_a_raw_grade(self):
        rows = [
            self._row(0, grade_flag=False, readability_grade=5),
            self._row(1, grade_flag=False, readability_grade=5),
            self._row(2, grade_flag=False, readability_grade=5),
            self._row(3, grade_flag=False, readability_grade=13),
        ]
        assert level_jumps({1: rows}) == []

    def test_sentence_length_is_shown_when_history_has_it(self):
        rows = [self._row(d, words_per_sentence=w) for d, w in enumerate((8.0, 9.0, 10.0))]
        rows.append(self._row(3, grade_flag=True, words=[], words_per_sentence=21.44))
        reason = level_jumps({1: rows})[0]["reasons"][0]
        assert reason["words_per_sentence"] == {"now": 21.4, "before": 9.0}

    def test_ai_jump_needs_three_earlier_scores(self):
        rows = [
            self._row(0),
            self._row(1),
            self._row(2, ai_probability=0.1),
            self._row(3, ai_probability=0.1),
            self._row(4, ai_probability=0.9),
        ]
        assert level_jumps({1: rows}) == []

    def test_steady_student(self):
        rows = [self._row(d, grade_flag=False, ai_probability=0.2) for d in range(4)]
        assert level_jumps({1: rows}) == []


@pytest.mark.django_db
class TestRadarEndpoint:
    def _setup(self, n_students=2):
        teacher = _teacher()
        classroom = Classroom.create_for(teacher, "History 8A")
        students = [UserFactory(is_verified=True) for _ in range(n_students)]
        for s in students:
            Membership.objects.create(classroom=classroom, user=s)
        return teacher, classroom, students

    def _member(self, classroom):
        student = UserFactory(is_verified=True)
        Membership.objects.create(classroom=classroom, user=student)
        return student

    def _work(self, classroom, student, seeds, spans=None):
        submission = SubmissionFactory(user=student, classroom=classroom, status=Submission.Status.COMPLETED, mime_type="text/plain")
        for position, seed in enumerate(seeds):
            vector = np.random.default_rng(seed).normal(size=EMBED_DIM)
            start, end = spans[position] if spans else (0, 1)
            SentenceVector.objects.create(
                submission=submission,
                position=position,
                start=start,
                end=end,
                language="en",
                embedding=(vector / np.linalg.norm(vector)).tolist(),
            )
        return submission

    def test_small_class_reports_not_enough_data(self):
        teacher, classroom, (a, b) = self._setup()
        self._work(classroom, a, [1, 2, 3, 4, 5])
        self._work(classroom, b, [1, 2, 3, 4, 6])
        response = _client(teacher).get(reverse("classroom-radar", args=[classroom.id]))
        assert response.status_code == 200
        assert response.data["skeleton_data"]["enough"] is False
        assert response.data["clusters"] == []

    def test_teacher_sees_shared_skeleton(self):
        teacher, classroom, students = self._setup(n_students=5)
        first = self._work(classroom, students[0], [1, 2, 3, 4, 5])
        second = self._work(classroom, students[1], [1, 2, 3, 4, 6])
        for k, s in enumerate(students[2:]):
            self._work(classroom, s, [100 * (k + 1) + j for j in range(5)])
        response = _client(teacher).get(reverse("classroom-radar", args=[classroom.id]))
        assert response.data["skeleton_data"]["enough"] is True
        assert response.data["clusters"] == [sorted([str(first.id), str(second.id)])]

    def test_jump_from_stored_evidence(self):
        teacher, classroom, (a, _) = self._setup()
        a.first_name, a.last_name = "Иван", "Морозов"
        a.save(update_fields=["first_name", "last_name"])
        grade = AnalyzerConfigFactory(name="text_grade_fit")
        verdicts = (
            (4, AnalysisResult.Verdict.INCONCLUSIVE),
            (3, AnalysisResult.Verdict.INCONCLUSIVE),
            (2, AnalysisResult.Verdict.INCONCLUSIVE),
            (1, AnalysisResult.Verdict.SUSPICIOUS),
        )
        for day, verdict in verdicts:
            work = SubmissionFactory(user=a, classroom=classroom, status=Submission.Status.COMPLETED, mime_type="text/plain")
            Submission.objects.filter(pk=work.pk).update(created_at=timezone.now() - timedelta(days=day))
            AnalysisResultFactory(
                submission=work, analyzer=grade, verdict=verdict, confidence=0.5,
                evidence={"readability_grade": 20, "beyond_level_words": ["идентичность", "цивилизация"]},
            )
        response = _client(teacher).get(reverse("classroom-radar", args=[classroom.id]), {"days": 30})
        assert response.data["days"] == 30
        assert [j["student"] for j in response.data["level_jumps"]] == ["Иван Морозов"]
        assert response.data["level_jumps"][0]["reasons"] == [{"kind": "vocabulary", "words": ["идентичность", "цивилизация"]}]

    def test_work_cleared_after_an_objection_leaves_the_radar(self):
        teacher, classroom, (a, _) = self._setup()
        grade = AnalyzerConfigFactory(name="text_grade_fit")
        last = None
        for day, verdict in ((4, "inconclusive"), (3, "inconclusive"), (2, "inconclusive"), (1, "suspicious")):
            last = SubmissionFactory(
                user=a, classroom=classroom, status=Submission.Status.COMPLETED, mime_type="text/plain", final_verdict="authentic",
            )
            Submission.objects.filter(pk=last.pk).update(created_at=timezone.now() - timedelta(days=day))
            AnalysisResultFactory(submission=last, analyzer=grade, verdict=verdict, confidence=0.5, evidence={})
        VerdictObjection.objects.create(
            submission=last, author=a, reason="Я писал сам.", status="answered", decision="changed", response="Работа своя.",
        )
        response = _client(teacher).get(reverse("classroom-radar", args=[classroom.id]), {"days": 30})
        assert response.data["level_jumps"] == []

    def test_pair_quotes_matching_sentences_from_the_text(self):
        teacher, classroom, students = self._setup(n_students=5)
        text = "Первое. Второе. Третье. Четвёртое. Пятое."
        spans = [(0, 7), (8, 15), (16, 23), (24, 34), (35, 41)]
        first = self._work(classroom, students[0], [1, 2, 3, 4, 5], spans=spans)
        TextFingerprint.objects.create(submission=first, text=text)
        second = self._work(classroom, students[1], [1, 2, 3, 4, 6], spans=spans)
        TextFingerprint.objects.create(submission=second, text=text)
        for k, s in enumerate(students[2:]):
            self._work(classroom, s, [100 * (k + 1) + j for j in range(5)])
        pair = _client(teacher).get(reverse("classroom-radar", args=[classroom.id])).data["shared_skeletons"][0]
        assert pair["a_matched"] == 4 and pair["a_sentences"] == 5
        assert len(pair["examples"]) == 3
        assert all(e["a"] == e["b"] and e["a"] in text for e in pair["examples"])

    def test_teacher_check_is_not_counted_as_a_student(self):
        teacher, classroom, students = self._setup(n_students=3)
        for k, s in enumerate(students):
            self._work(classroom, s, [100 * (k + 1) + j for j in range(5)])
        sheet = self._work(classroom, teacher, [1, 2, 3, 4, 5])
        self._work(classroom, teacher, [700 + j for j in range(5)])
        data = _client(teacher).get(reverse("classroom-radar", args=[classroom.id])).data
        assert data["skeleton_data"]["students"] == 3 and data["skeleton_data"]["enough"] is False
        assert data["compared"] == 5 and data["submissions"] == 5
        copy = self._work(classroom, students[0], [1, 2, 3, 4, 6])
        self._work(classroom, self._member(classroom), [900 + j for j in range(5)])
        data = _client(teacher).get(reverse("classroom-radar", args=[classroom.id])).data
        refs = {ref["submission_id"]: ref for p in data["shared_skeletons"] for ref in (p["a"], p["b"])}
        assert refs[str(sheet.id)]["unattributed"] is True and refs[str(sheet.id)]["student"] == ""
        assert refs[str(copy.id)]["unattributed"] is False

    def test_student_cannot_open_radar(self):
        _, classroom, (a, _) = self._setup()
        assert _client(a).get(reverse("classroom-radar", args=[classroom.id])).status_code == 403
