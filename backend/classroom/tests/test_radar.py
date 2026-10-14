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
from classroom.radar import Doc, alignment, clusters, level_jumps, shared_skeletons
from content.models import Submission
from content.tests.factories import SubmissionFactory
from plagiarism.models import EMBED_DIM, SentenceVector
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

    def test_clusters_join_chains(self):
        pairs = [
            {"a": {"submission_id": "x"}, "b": {"submission_id": "y"}},
            {"a": {"submission_id": "y"}, "b": {"submission_id": "z"}},
            {"a": {"submission_id": "p"}, "b": {"submission_id": "q"}},
        ]
        assert clusters(pairs) == [["x", "y", "z"], ["p", "q"]]


class TestLevelJumps:
    def _row(self, day, **fields):
        return {"submission_id": f"w{day}", "student": "kid", "created_at": timezone.now() + timedelta(days=day), **fields}

    def test_readability_and_ai_jump(self):
        rows = [
            self._row(0, readability_grade=5, ai_probability=0.1),
            self._row(1, readability_grade=6, ai_probability=0.2),
            self._row(2, readability_grade=11, ai_probability=0.9),
        ]
        jumps = level_jumps({1: rows})
        assert len(jumps) == 1 and jumps[0]["submission_id"] == "w2"
        assert len(jumps[0]["reasons"]) == 2

    def test_needs_two_earlier_works(self):
        rows = [self._row(0, readability_grade=5), self._row(1, readability_grade=11)]
        assert level_jumps({1: rows}) == []

    def test_steady_student(self):
        rows = [self._row(d, readability_grade=7, ai_probability=0.2) for d in range(4)]
        assert level_jumps({1: rows}) == []


@pytest.mark.django_db
class TestRadarEndpoint:
    def _setup(self):
        teacher = _teacher()
        classroom = Classroom.create_for(teacher, "History 8A")
        students = [UserFactory(is_verified=True) for _ in range(2)]
        for s in students:
            Membership.objects.create(classroom=classroom, user=s)
        return teacher, classroom, students

    def _work(self, classroom, student, seeds):
        submission = SubmissionFactory(user=student, classroom=classroom, status=Submission.Status.COMPLETED, mime_type="text/plain")
        for position, seed in enumerate(seeds):
            vector = np.random.default_rng(seed).normal(size=EMBED_DIM)
            SentenceVector.objects.create(
                submission=submission,
                position=position,
                start=0,
                end=1,
                language="en",
                embedding=(vector / np.linalg.norm(vector)).tolist(),
            )
        return submission

    def test_teacher_sees_shared_skeleton(self):
        teacher, classroom, (a, b) = self._setup()
        first = self._work(classroom, a, [1, 2, 3, 4, 5])
        second = self._work(classroom, b, [1, 2, 3, 4, 6])
        response = _client(teacher).get(reverse("classroom-radar", args=[classroom.id]))
        assert response.status_code == 200
        assert response.data["submissions"] == 2
        assert response.data["clusters"] == [sorted([str(first.id), str(second.id)])]

    def test_jump_from_stored_evidence(self):
        teacher, classroom, (a, _) = self._setup()
        grade = AnalyzerConfigFactory(name="text_grade_fit")
        for day, level in ((3, 5), (2, 6), (1, 11)):
            work = SubmissionFactory(user=a, classroom=classroom, status=Submission.Status.COMPLETED, mime_type="text/plain")
            Submission.objects.filter(pk=work.pk).update(created_at=timezone.now() - timedelta(days=day))
            AnalysisResultFactory(
                submission=work, analyzer=grade, verdict=AnalysisResult.Verdict.INCONCLUSIVE, confidence=0.5, evidence={"readability_grade": level}
            )
        response = _client(teacher).get(reverse("classroom-radar", args=[classroom.id]), {"days": 30})
        assert response.data["days"] == 30
        assert [j["student"] for j in response.data["level_jumps"]] == [a.username]

    def test_student_cannot_open_radar(self):
        _, classroom, (a, _) = self._setup()
        assert _client(a).get(reverse("classroom-radar", args=[classroom.id])).status_code == 403
