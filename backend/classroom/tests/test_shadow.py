from unittest import mock

import numpy as np
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from analyzers.implementations.text_signals import TextShadowAnalyzer
from billing.models import Subscription, get_or_create_subscription
from classroom import shadow as shadow_module
from classroom.models import Classroom, Membership, ShadowAnswer, ShadowSet
from classroom.shadow import DAILY_SETS, best_match, build, prompt_language, variants
from classroom.tasks import build_shadow_set
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory

SENTENCES = [
    "Books build imagination in a way screens rarely do for young readers.",
    "Reading every day also grows the vocabulary that students need for exams.",
    "Many people say the internet replaces books, but it mostly offers short fragments.",
    "A long novel teaches patience and the habit of following a complex idea.",
    "So reading still matters today, perhaps even more than before.",
]
ESSAY = " ".join(SENTENCES)
OTHER = (
    "My grandmother lives in a small village near the river. We often go fishing there in summer. "
    "Last year we caught a pike that was almost a metre long. Grandpa showed us how to fix the old bike. "
    "In the evening we sat by the fire and looked at the stars."
)


def fake_embed(sentences):
    vectors = []
    for s in sentences:
        v = np.random.default_rng(sum(map(ord, s))).normal(size=16)
        vectors.append((v / np.linalg.norm(v)).tolist())
    return vectors


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _class():
    teacher = UserFactory(is_verified=True)
    sub = get_or_create_subscription(teacher)
    sub.tier = Subscription.Tier.EDUCATION
    sub.save(update_fields=["tier"])
    classroom = Classroom.create_for(teacher, "Literature 9B")
    student = UserFactory(is_verified=True)
    Membership.objects.create(classroom=classroom, user=student)
    return teacher, classroom, student


def _done_set(classroom):
    shadow = ShadowSet.objects.create(classroom=classroom, prompt="Is reading still important today?", language="en", status=ShadowSet.Status.DONE)
    ShadowAnswer.objects.create(shadow_set=shadow, text=ESSAY, variant="9th grade", vectors=fake_embed(SENTENCES))
    return shadow


class TestVariants:
    def test_variants_cover_grades_and_are_stable(self):
        a = variants("ru", 8, "seed")
        assert a == variants("ru", 8, "seed")
        assert {v["grade"] for v in a} == set(shadow_module.GRADES["ru"])

    def test_prompt_language(self):
        assert prompt_language("Напишите сочинение о роли книг в жизни человека") == "ru"
        assert prompt_language("Write an essay about the role of books in our lives") == "en"
        assert prompt_language("???", default="fr") == "fr"


@pytest.mark.django_db
class TestBuildAndMatch:
    def test_build_stores_answers_with_vectors(self):
        _, classroom, _ = _class()
        shadow = ShadowSet.objects.create(classroom=classroom, prompt="Is reading still important today?", language="en", target=2)
        with mock.patch.object(shadow_module, "_generate", return_value=ESSAY), mock.patch.object(shadow_module, "embed", side_effect=fake_embed):
            assert build(shadow) == 2
        assert shadow.answers.count() == 2 and len(shadow.answers.first().vectors) == 5

    def test_task_marks_failure_when_model_is_down(self):
        _, classroom, _ = _class()
        shadow = ShadowSet.objects.create(classroom=classroom, prompt="Is reading still important today?", language="en", target=2)
        with mock.patch.object(shadow_module, "_generate", side_effect=ConnectionError("ollama down")):
            build_shadow_set(str(shadow.id))
        shadow.refresh_from_db()
        assert shadow.status == ShadowSet.Status.FAILED and shadow.error

    def test_same_answer_matches_and_other_text_does_not(self):
        _, classroom, _ = _class()
        answer = _done_set(classroom).answers.first()
        with mock.patch.object(shadow_module, "embed", side_effect=fake_embed):
            match = best_match(ESSAY, [answer])
            other = best_match(OTHER, [answer])
        assert match["flagged"] and match["share"] == 1.0 and match["in_order"] == 1.0
        assert len(match["pairs"]) == 3 and match["answers_compared"] == 1
        assert not other["flagged"]


@pytest.mark.django_db
class TestShadowAnalyzer:
    def _run(self, tmp_path, submission, text=ESSAY):
        path = tmp_path / "essay.txt"
        path.write_text(text)
        with mock.patch.object(shadow_module, "embed", side_effect=fake_embed):
            return TextShadowAnalyzer().analyze(str(path), {"mime_type": "text/plain", "submission_id": str(submission.id)})

    def test_flags_a_copy_of_an_ai_answer(self, tmp_path):
        _, classroom, student = _class()
        _done_set(classroom)
        out = self._run(tmp_path, SubmissionFactory(user=student, classroom=classroom, mime_type="text/plain"))
        assert out.verdict == "suspicious" and out.evidence["context_signal"]

    def test_own_text_is_not_flagged(self, tmp_path):
        _, classroom, student = _class()
        _done_set(classroom)
        out = self._run(tmp_path, SubmissionFactory(user=student, classroom=classroom, mime_type="text/plain"), OTHER)
        assert out.verdict == "inconclusive"

    def test_abstains_without_shadows_or_class(self, tmp_path):
        _, classroom, student = _class()
        assert self._run(tmp_path, SubmissionFactory(user=student, classroom=classroom)).evidence["reason"].startswith("no AI answers")
        assert self._run(tmp_path, SubmissionFactory(user=student)).evidence["reason"] == "not a class submission"


@pytest.mark.django_db
class TestShadowEndpoints:
    def test_teacher_creates_and_lists(self):
        teacher, classroom, _ = _class()
        url = reverse("classroom-shadows", args=[classroom.id])
        with mock.patch("classroom.views.build_shadow_set.delay"):
            response = _client(teacher).post(url, {"prompt": "Напишите сочинение: нужно ли читать книги?", "target": 4}, format="json")
        assert response.status_code == 201
        assert response.data["language"] == "ru" and response.data["target"] == 4
        assert [s["id"] for s in _client(teacher).get(url).data] == [response.data["id"]]

    def test_daily_limit(self):
        teacher, classroom, _ = _class()
        for _ in range(DAILY_SETS):
            ShadowSet.objects.create(classroom=classroom, prompt="Is reading still important?", language="en")
        url = reverse("classroom-shadows", args=[classroom.id])
        assert _client(teacher).post(url, {"prompt": "Is reading still important today?"}, format="json").status_code == 429

    def test_student_cannot_create_or_read(self):
        _, classroom, student = _class()
        url = reverse("classroom-shadows", args=[classroom.id])
        assert _client(student).post(url, {"prompt": "Is reading still important today?"}, format="json").status_code == 403
        assert _client(student).get(url).status_code == 403

    def test_detail_and_delete(self):
        teacher, classroom, _ = _class()
        shadow = _done_set(classroom)
        url = reverse("classroom-shadow-detail", args=[classroom.id, shadow.id])
        assert _client(teacher).get(url).data["texts"][0]["variant"] == "9th grade"
        assert _client(teacher).delete(url).status_code == 204
        assert not ShadowSet.objects.filter(id=shadow.id).exists()
