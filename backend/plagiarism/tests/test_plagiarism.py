import hashlib
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.test import override_settings

from classroom.models import Classroom, Membership, Organization
from content.tasks import queue_originality_check
from content.tests.factories import SubmissionFactory
from plagiarism.embeddings import EmbeddingsUnavailable
from plagiarism.models import PlagiarismReport
from plagiarism.search import Hit
from plagiarism.serializers import report_payload
from plagiarism.service import run_check
from plagiarism.shingles import covered_spans, shingle_hashes, tokenize, winnow
from users.tests.factories import UserFactory

ESSAY = (
    "Декомпозиция сложной задачи позволяет разделить работу на понятные и небольшие части. "
    "Каждую часть можно решать отдельно, проверяя результат на каждом шаге работы. "
    "Такой подход помогает не запутаться и видеть, сколько работы уже сделано. "
    "В конце все части собираются вместе, и задача оказывается решённой полностью."
)
OWN = (
    "Мы с классом ходили в музей и смотрели на старинные машины и паровозы. "
    "Больше всего мне понравился огромный красный паровоз с блестящими колёсами. "
    "Экскурсовод рассказал, что он возил людей через всю страну много лет назад."
)
TRANSLATED_SENTENCE = "Decomposition of a complex task lets you split the work into clear and small parts."


def _vector(seed: str) -> list[float]:
    digest = hashlib.sha256(seed.encode()).digest()
    raw = [b - 128 for b in (digest * 12)[:384]]
    norm = sum(x * x for x in raw) ** 0.5
    return [x / norm for x in raw]


def fake_embed(sentences):
    out = []
    for s in sentences:
        key = "decomposition" if ("Декомпозиция" in s or "Decomposition" in s) else s
        out.append(_vector(key))
    return out


def _class(level=8):
    return Classroom.create_for(UserFactory(), "Class", level=level)


def _text_submission(user, text, classroom=None, name="essay.txt", personal=False):
    if classroom is None and not personal:
        classroom = _class()
    return SubmissionFactory(
        user=user, classroom=classroom, mime_type="text/plain", original_filename=name,
        file=ContentFile(text.encode("utf-8"), name=name),
    )


class TestShingles:
    def test_obfuscated_copy_still_matches(self):
        clean = tokenize(ESSAY)
        dirty_text = ESSAY.replace("а", "a").replace("задачи", "за​дачи")
        dirty = tokenize(dirty_text)
        spans = covered_spans(dirty, shingle_hashes(dirty), set(shingle_hashes(clean)))
        assert sum(e - s for s, e in spans) > 0.9 * len(dirty_text)

    def test_winnowing_is_deterministic_and_smaller(self):
        hashes = shingle_hashes(tokenize(ESSAY))
        assert winnow(hashes) == winnow(list(hashes))
        assert 0 < len(winnow(hashes)) < len(hashes)


@pytest.mark.django_db
@patch("plagiarism.service.embed", side_effect=fake_embed)
class TestRunCheck:
    def test_copy_from_another_student_is_found(self, _embed):
        source = _text_submission(UserFactory(), ESSAY)
        run_check(source)
        copier = _text_submission(UserFactory(), OWN + " " + ESSAY)
        report = run_check(copier)
        assert report.status == PlagiarismReport.Status.DONE
        exact = [m for m in report.matches if m["kind"] == "exact"]
        assert exact and exact[0]["submission_id"] == str(source.id)
        assert 30 < report.originality < 60

    def test_original_work_scores_full_originality(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY))
        report = run_check(_text_submission(UserFactory(), OWN))
        assert report.matches == []
        assert report.originality == 100.0

    def test_resubmitting_your_own_work_is_not_plagiarism(self, _embed):
        student = UserFactory()
        run_check(_text_submission(student, ESSAY))
        assert run_check(_text_submission(student, ESSAY)).originality == 100.0

    def test_translation_is_found_semantically(self, _embed):
        source = _text_submission(UserFactory(), ESSAY)
        run_check(source)
        report = run_check(_text_submission(UserFactory(), OWN + " " + TRANSLATED_SENTENCE))
        kinds = {m["kind"] for m in report.matches}
        assert "translation" in kinds
        assert report.originality < 100

    @override_settings(PLAGIARISM_WEB_ENABLED=True)
    @patch("plagiarism.web.fetch_text", return_value="Some page. " + ESSAY + " Footer.")
    @patch("plagiarism.web.search", return_value=[Hit("https://example.org/essay", "Essay site", "")])
    def test_web_source_is_reported(self, _search, _fetch, _embed):
        report = run_check(_text_submission(UserFactory(), ESSAY, personal=True))
        web = [m for m in report.matches if m["source"] == "web"]
        assert web and web[0]["url"] == "https://example.org/essay"
        assert report.originality < 10
        assert report.web_searched

    @override_settings(PLAGIARISM_WEB_ENABLED=True, PLAGIARISM_WIKIPEDIA=True)
    @patch("plagiarism.web.fetch_text", return_value="Article intro. " + ESSAY + " See also.")
    @patch("plagiarism.web.search", return_value=[])
    @patch("plagiarism.search.requests.get")
    def test_wikipedia_is_searched_even_when_web_search_finds_nothing(self, get, _search, _fetch, _embed):
        get.return_value.json.return_value = {"query": {"search": [{"title": "Sleep and memory"}]}}
        get.return_value.raise_for_status.return_value = None
        report = run_check(_text_submission(UserFactory(), ESSAY, personal=True))
        web = [m for m in report.matches if m["source"] == "web"]
        assert web and web[0]["url"].endswith(".wikipedia.org/wiki/Sleep_and_memory")
        assert get.call_args.kwargs["params"]["srsearch"].startswith('"')


def _org_class(web_search_enabled):
    owner = UserFactory()
    org = Organization.create_for(owner, "Lyceum", f"lyceum-{owner.id}")
    org.web_search_enabled = web_search_enabled
    org.save(update_fields=["web_search_enabled"])
    return Classroom.create_for(owner, "9A", organization=org)


@pytest.mark.django_db
@patch("plagiarism.service.embed", side_effect=fake_embed)
@patch("plagiarism.web.fetch_text", return_value="")
@patch("plagiarism.web.search", return_value=[Hit("https://example.org/essay", "Essay site", "")])
class TestWebSearchPolicy:
    @pytest.fixture(autouse=True)
    def _web_on(self, settings):
        settings.PLAGIARISM_WEB_ENABLED = True

    def test_org_class_work_is_not_searched_by_default(self, search, _fetch, _embed):
        report = run_check(_text_submission(UserFactory(), ESSAY, _org_class(False)))
        assert report.status == PlagiarismReport.Status.DONE
        search.assert_not_called()
        assert not report.web_searched
        assert report.web_queries == 0

    def test_org_class_work_is_searched_when_the_school_allows_it(self, search, _fetch, _embed):
        report = run_check(_text_submission(UserFactory(), ESSAY, _org_class(True)))
        assert search.called
        assert report.web_searched

    def test_personal_upload_is_searched(self, search, _fetch, _embed):
        report = run_check(_text_submission(UserFactory(), ESSAY, personal=True))
        assert search.called
        assert report.web_searched

    def test_class_without_organization_is_not_searched(self, search, _fetch, _embed):
        report = run_check(_text_submission(UserFactory(), ESSAY, _class()))
        assert report.status == PlagiarismReport.Status.DONE
        search.assert_not_called()
        assert not report.web_searched

    def test_global_switch_off_wins_over_school_setting(self, search, _fetch, _embed, settings):
        settings.PLAGIARISM_WEB_ENABLED = False
        run_check(_text_submission(UserFactory(), ESSAY, _org_class(True)))
        run_check(_text_submission(UserFactory(), ESSAY, personal=True))
        search.assert_not_called()


@pytest.mark.django_db
@patch("plagiarism.service.embed", side_effect=fake_embed)
class TestReportPrivacy:
    def test_teacher_sees_classmate_source_outsider_does_not(self, _embed):
        teacher = UserFactory()
        classroom = Classroom.create_for(teacher, "8A", level=8)
        a, b = UserFactory(), UserFactory()
        for s in (a, b):
            Membership.objects.create(classroom=classroom, user=s)
        source = _text_submission(a, ESSAY, classroom)
        run_check(source)
        copy = _text_submission(b, ESSAY, classroom)
        run_check(copy)
        copy.refresh_from_db()
        teacher_view = report_payload(copy, teacher)["matches"][0]
        assert teacher_view["author"] == a.username
        assert teacher_view["excerpts"]
        student_view = report_payload(copy, b)["matches"][0]
        assert student_view["title"] == "Another ProofLayer submission"
        assert "author" not in student_view


@pytest.mark.django_db
@patch("plagiarism.service.embed", side_effect=fake_embed)
class TestRepository:
    def test_personal_checks_are_compared_but_not_stored(self, _embed):
        personal = _text_submission(UserFactory(), ESSAY, personal=True)
        run_check(personal)
        assert not personal.text_fingerprint.in_repository
        assert not personal.sentence_vectors.exists()
        report = run_check(_text_submission(UserFactory(), ESSAY))
        assert report.originality == 100.0

    def test_personal_check_still_finds_class_sources(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY))
        report = run_check(_text_submission(UserFactory(), ESSAY, personal=True))
        assert report.originality < 10


@pytest.mark.django_db
@patch("plagiarism.service.embed", side_effect=EmbeddingsUnavailable("torch missing"))
class TestWithoutEmbeddings:
    def test_exact_matching_still_works(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY))
        report = run_check(_text_submission(UserFactory(), ESSAY))
        assert report.status == PlagiarismReport.Status.DONE
        assert report.originality < 10


@pytest.mark.django_db
class TestQueueing:
    @patch("content.tasks.current_app.send_task")
    def test_only_text_and_documents_are_queued(self, send_task):
        queue_originality_check(SubmissionFactory(mime_type="image/jpeg"))
        assert not send_task.called
        text = SubmissionFactory(mime_type="text/plain")
        queue_originality_check(text)
        send_task.assert_called_once_with("plagiarism.tasks.check_submission", args=[str(text.id)])
        assert PlagiarismReport.objects.get(submission=text).status == PlagiarismReport.Status.PENDING
