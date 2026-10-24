import hashlib
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.db import connection
from django.test import override_settings

from classroom.models import Classroom, Membership, Organization, ShadowSet
from content.tasks import queue_originality_check
from content.tests.factories import SubmissionFactory
from plagiarism.embeddings import EmbeddingsUnavailable
from plagiarism.models import PlagiarismReport, TextFingerprint
from plagiarism.search import Hit
from plagiarism.serializers import report_payload
from plagiarism.service import run_check
from plagiarism.shingles import (
    copied_pairs,
    covered_spans,
    covered_token_chars,
    shingle_hashes,
    text_chars,
    tokenize,
    winnow,
)
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
ESSAY_FIRST = "Декомпозиция сложной задачи позволяет разделить работу на понятные и небольшие части."
ESSAY_THIRD = "Такой подход помогает не запутаться и видеть, сколько работы уже сделано."
OWN_FIRST = "Мы с классом ходили в музей и смотрели на старинные машины и паровозы."
OWN_SECOND = "Больше всего мне понравился огромный красный паровоз с блестящими колёсами."
COPIED_INSIDE = (
    "Я где-то прочитал, что декомпозиция сложной задачи позволяет разделить работу на понятные и небольшие части."
)
BEARD_SOURCE = "При Петре бояр заставляли брить бороды, а кто не хотел, тот платил налог за бороду."
BEARD_OWN = "Мне запомнилось, что бояр заставляли брить бороды, а кто не хотел, тот платил налог."
TRAIN_SOURCE = "Старый паровоз когда-то перевозил почту и грузы между далёкими северными городами."
TRAIN_REWORDED = "Этот локомотив раньше доставлял письма и товары между отдалёнными городами севера."
CLOCK_SOURCE = "На вокзале нам показали огромные часы, которые работают уже больше ста лет."
CLOCK_REWORDED = "Ещё мы видели вокзальные часы, они идут без остановки целое столетие."
QUESTION = "Почему Катерина не может жить так же спокойно и весело, как живёт её подруга Варвара в доме Кабановых?"
ANSWERS = [
    "Мне кажется, что героиня слишком честная и совсем не умеет притворяться перед людьми.",
    "Она выросла в доме, где её любили, поэтому чужая строгость её очень сильно ранит.",
    "Варвара привыкла хитрить с детства, а у Катерины совсем другой характер и воспитание.",
    "Для меня главное в пьесе то, что любая неправда для Катерины равна настоящему греху.",
]


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


def _near(seed: str, similarity: float) -> list[float]:
    base = _vector(seed)
    other = _vector(seed + " other")
    dot = sum(x * y for x, y in zip(base, other))
    side = [y - dot * x for x, y in zip(base, other)]
    norm = sum(x * x for x in side) ** 0.5
    rest = (1 - similarity * similarity) ** 0.5
    return [similarity * x + rest * y / norm for x, y in zip(base, side)]


def _embed_with(pairs: dict[str, list[float]]):
    def embed(sentences):
        return [next((v for key, v in pairs.items() if key in s), None) or fake_embed([s])[0] for s in sentences]
    return embed


WEB_MATCH = {"source": "web", "kind": "exact", "url": "https://example.org", "title": "Site", "spans": [[0, 20]]}


def _blocked_engine(query, limit):
    raise RuntimeError("blocked")


REWORDED_AT_096 = {
    "перевозил почту": _vector("train"),
    "доставлял письма": _near("train", 0.96),
    "огромные часы": _vector("clock"),
    "вокзальные часы": _near("clock", 0.96),
}


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

    def test_one_stock_phrase_is_not_a_copied_passage(self):
        own = tokenize("Я считаю, что спорт полезен по нескольким причинам. Во-первых, он укрепляет здоровье.")
        stock = tokenize("Мне нравится лето по нескольким причинам. Во-первых, можно долго гулять с друзьями.")
        longer = tokenize("Плавание тоже полезно по нескольким причинам. Во-первых, он укрепляет здоровье.")
        assert covered_spans(own, shingle_hashes(own), set(shingle_hashes(stock))) == []
        assert len(covered_spans(own, shingle_hashes(own), set(shingle_hashes(longer)))) == 1

    def test_links_and_doi_are_not_words(self):
        tokens = tokenize(
            "См. https://doi.org/10.1016/j.cell.2020.01.001 и www.example.com/a, а также doi: 10.1038/nature123 здесь"
        )
        assert [t.norm for t in tokens] == ["см", "и", "а", "также", "здесь"]

    def test_copied_and_total_characters_use_the_same_unit(self):
        text = "Один,   два и три!  Четыре; пять."
        tokens = tokenize(text)
        assert covered_token_chars(tokens, [(0, len(text))]) == text_chars(tokens)
        assert covered_token_chars(tokens, [(tokens[0].start, tokens[3].end)]) == len("Одиндваитри")

    def test_source_passage_keeps_a_word_the_copier_left_out(self):
        own_text = "один два три четыре пять шесть семь восемь девять десять одиннадцать двенадцать"
        source_text = "ноль один два три четыре пять шесть лишнее семь восемь девять десять одиннадцать двенадцать конец"
        own = tokenize(own_text)
        [(own_span, source_span)] = copied_pairs(own, shingle_hashes(own), tokenize(source_text))
        assert own_text[own_span[0]:own_span[1]] == own_text
        assert source_text[source_span[0]:source_span[1]] == (
            "один два три четыре пять шесть лишнее семь восемь девять десять одиннадцать двенадцать"
        )

    def test_source_passage_does_not_swallow_the_text_between_two_copied_parts(self):
        own_text = "альфа бета гамма дельта эпсилон дзета эта тета йота каппа лямбда мю"
        filler = " ".join(f"слово{n}" for n in range(20))
        source_text = f"альфа бета гамма дельта эпсилон дзета {filler} эта тета йота каппа лямбда мю"
        own = tokenize(own_text)
        [(_, source_span)] = copied_pairs(own, shingle_hashes(own), tokenize(source_text))
        assert source_span[1] - source_span[0] < len(own_text) + 60


@pytest.mark.django_db
@patch("plagiarism.service.embed", side_effect=fake_embed)
class TestRunCheck:
    @pytest.fixture(autouse=True)
    def _exact_nearest_sentences(self, db):
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_indexscan = off")

    def test_copy_from_another_student_is_found(self, _embed):
        source = _text_submission(UserFactory(), ESSAY)
        run_check(source)
        copier = _text_submission(UserFactory(), OWN + " " + ESSAY)
        report = run_check(copier)
        assert report.status == PlagiarismReport.Status.DONE
        exact = [m for m in report.matches if m["kind"] == "exact"]
        assert exact and exact[0]["submission_id"] == str(source.id)
        assert 30 < report.originality < 60

    def test_whole_copy_is_zero_originality_and_the_full_share(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY))
        copy = _text_submission(UserFactory(), ESSAY)
        report = run_check(copy)
        assert report.originality == 0.0
        assert report.matched_chars == report.total_chars == text_chars(tokenize(ESSAY))
        assert report.matches[0]["matched_chars"] == report.matched_chars
        copy.refresh_from_db()
        row = report_payload(copy, UserFactory(is_staff=True))["matches"][0]
        assert row["share"] == 100.0
        assert row["source_excerpts"] == row["excerpts"]

    def test_partial_copy_percentage_matches_the_share_of_words(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY))
        text = " ".join([ESSAY_FIRST, OWN_FIRST, ESSAY_THIRD, OWN_SECOND])
        copy = _text_submission(UserFactory(), text)
        report = run_check(copy)
        copied = text_chars(tokenize(ESSAY_FIRST)) + text_chars(tokenize(ESSAY_THIRD))
        expected = 100 * (1 - copied / text_chars(tokenize(text)))
        assert abs(report.originality - expected) < 2
        assert report.matches[0]["matched_chars"] == report.matched_chars == copied
        copy.refresh_from_db()
        payload = report_payload(copy, UserFactory(is_staff=True))
        assert len(payload["matches"]) == 1
        assert payload["matches"][0]["share"] <= 100 - round(report.originality)
        assert payload["matches"][0]["excerpts"] == [ESSAY_FIRST[:-1], ESSAY_THIRD[:-1]]

    def test_a_short_shared_phrase_is_not_copying(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY + " " + BEARD_SOURCE))
        report = run_check(_text_submission(UserFactory(), OWN + " " + BEARD_OWN))
        assert report.matches == []
        assert report.originality == 100.0

    def test_reworded_sentence_counts_with_an_exact_hit_from_the_same_source(self, embed):
        embed.side_effect = _embed_with(REWORDED_AT_096)
        source = _text_submission(UserFactory(), ESSAY + " " + TRAIN_SOURCE)
        run_check(source)
        text = " ".join([COPIED_INSIDE, OWN_FIRST, TRAIN_REWORDED])
        copy = _text_submission(UserFactory(), text)
        report = run_check(copy)
        assert len(report.matches) == 1
        match = report.matches[0]
        assert match["submission_id"] == str(source.id)
        assert match["kinds"] == ["exact", "paraphrase"]
        copied = text_chars(tokenize(ESSAY_FIRST)) + text_chars(tokenize(TRAIN_REWORDED))
        expected = 100 * (1 - copied / text_chars(tokenize(text)))
        assert abs(report.originality - expected) < 1
        copy.refresh_from_db()
        row = report_payload(copy, UserFactory(is_staff=True))["matches"][0]
        assert TRAIN_REWORDED in row["excerpts"]
        assert row["source_excerpts"][row["excerpts"].index(TRAIN_REWORDED)] == TRAIN_SOURCE
        assert row["excerpt_kinds"][row["excerpts"].index(TRAIN_REWORDED)] == "paraphrase"

    def test_one_similar_sentence_alone_is_not_copying(self, embed):
        embed.side_effect = _embed_with(REWORDED_AT_096)
        run_check(_text_submission(UserFactory(), ESSAY + " " + TRAIN_SOURCE))
        report = run_check(_text_submission(UserFactory(), OWN + " " + TRAIN_REWORDED))
        assert report.matches == []
        assert report.originality == 100.0

    def test_scattered_similar_sentences_are_not_copying(self, embed):
        embed.side_effect = _embed_with(REWORDED_AT_096)
        run_check(_text_submission(UserFactory(), " ".join([ESSAY, TRAIN_SOURCE, CLOCK_SOURCE])))
        report = run_check(_text_submission(UserFactory(), " ".join([TRAIN_REWORDED, OWN, CLOCK_REWORDED])))
        assert report.matches == []

    def test_consecutive_reworded_sentences_are_found(self, embed):
        embed.side_effect = _embed_with(REWORDED_AT_096)
        source = _text_submission(UserFactory(), " ".join([ESSAY, TRAIN_SOURCE, CLOCK_SOURCE]))
        run_check(source)
        text = " ".join([OWN, TRAIN_REWORDED, CLOCK_REWORDED])
        report = run_check(_text_submission(UserFactory(), text))
        assert [(m["submission_id"], m["kind"]) for m in report.matches] == [(str(source.id), "paraphrase")]
        expected = 100 * text_chars(tokenize(OWN)) / text_chars(tokenize(text))
        assert abs(report.originality - expected) < 1

    def test_assignment_wording_shared_by_the_class_is_not_copying(self, _embed):
        classroom = _class()
        first = run_check(_text_submission(UserFactory(), QUESTION + " " + ANSWERS[0], classroom))
        second = run_check(_text_submission(UserFactory(), QUESTION + " " + ANSWERS[1], classroom))
        run_check(_text_submission(UserFactory(), QUESTION + " " + ANSWERS[2], classroom))
        fourth = run_check(_text_submission(UserFactory(), QUESTION + " " + ANSWERS[3], classroom))
        assert first.matches == [] and second.matches
        assert fourth.matches == []
        assert fourth.originality == 100.0

    def test_wording_of_the_teacher_prompt_is_not_copying(self, _embed):
        classroom = _class()
        ShadowSet.objects.create(classroom=classroom, prompt=QUESTION, language="ru")
        run_check(_text_submission(UserFactory(), QUESTION + " " + ANSWERS[0], classroom))
        report = run_check(_text_submission(UserFactory(), QUESTION + " " + ANSWERS[1], classroom))
        assert report.matches == []
        assert report.originality == 100.0

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

    def test_shared_bibliography_is_not_counted_as_copying(self, _embed):
        books = (
            "\n\nСписок литературы\n"
            "Лотман Ю. М. Беседы о русской культуре: Быт и традиции русского дворянства (XVIII – начало XIX века). СПб.: Искусство-СПБ, 1994.\n"
            "Бочаров С. Г. Роман Л. Толстого «Война и мир». М.: Художественная литература, 1978."
        )
        run_check(_text_submission(UserFactory(), ESSAY + books))
        report = run_check(_text_submission(UserFactory(), OWN + books))
        assert report.matches == []
        assert report.originality == 100.0

    def test_same_topic_sentences_below_the_paraphrase_bar_are_not_listed(self, embed):
        embed.side_effect = _embed_with({
            "Декомпозиция сложной": _vector("topic 1"),
            "Каждую часть": _vector("topic 2"),
            "Такой подход": _vector("topic 3"),
            "Мы с классом": _near("topic 1", 0.94),
            "Больше всего": _near("topic 2", 0.94),
            "Экскурсовод": _near("topic 3", 0.94),
        })
        run_check(_text_submission(UserFactory(), ESSAY))
        report = run_check(_text_submission(UserFactory(), OWN))
        assert report.matches == []

    @override_settings(PLAGIARISM_WEB_ENABLED=True)
    @patch("plagiarism.web.fetch_text", return_value="Some page.\n" + ESSAY + "\nFooter.")
    @patch("plagiarism.web.lookup", return_value=([Hit("https://example.org/essay", "Essay site", "")], True))
    def test_web_source_is_reported(self, _lookup, _fetch, _embed):
        submission = _text_submission(UserFactory(), ESSAY, personal=True)
        report = run_check(submission)
        web = [m for m in report.matches if m["source"] == "web"]
        assert web and web[0]["url"] == "https://example.org/essay"
        assert report.originality < 10
        assert report.web_searched
        assert report.web_status == PlagiarismReport.WebStatus.OK
        assert report.web_engines == ["web"]
        submission.refresh_from_db()
        row = report_payload(submission, submission.user)["matches"][0]
        assert row["source_excerpts"]
        assert all(passage and passage.rstrip("…") in ESSAY for passage in row["source_excerpts"])
        assert row["hidden"] is False

    @override_settings(PLAGIARISM_WEB_ENABLED=True, PLAGIARISM_WIKIPEDIA=True)
    @patch("plagiarism.web.fetch_text", return_value="Article intro. " + ESSAY + " See also.")
    @patch("plagiarism.web.lookup", return_value=([], False))
    @patch("plagiarism.search.requests.get")
    def test_wikipedia_is_searched_even_when_web_search_finds_nothing(self, get, _lookup, _fetch, _embed):
        get.return_value.json.return_value = {"query": {"search": [{"title": "Sleep and memory"}]}}
        get.return_value.raise_for_status.return_value = None
        report = run_check(_text_submission(UserFactory(), ESSAY, personal=True))
        web = [m for m in report.matches if m["source"] == "web"]
        assert web and web[0]["url"].endswith(".wikipedia.org/wiki/Sleep_and_memory")
        assert get.call_args.kwargs["params"]["srsearch"].startswith('"')
        assert report.web_searched
        assert report.web_engines == ["wikipedia"]

    @override_settings(PLAGIARISM_WEB_ENABLED=True, PLAGIARISM_WIKIPEDIA=True, PLAGIARISM_SEARCH_PROVIDERS=["ddg"])
    @patch("plagiarism.web.fetch_text")
    @patch("plagiarism.search.PROVIDERS", {"ddg": _blocked_engine})
    @patch("plagiarism.search.requests.get", side_effect=ConnectionError("offline"))
    def test_search_that_never_answered_is_not_reported_as_done(self, _get, fetch, _embed):
        submission = _text_submission(UserFactory(), ESSAY, personal=True)
        report = run_check(submission)
        assert report.status == PlagiarismReport.Status.DONE
        assert report.web_status == PlagiarismReport.WebStatus.FAILED
        assert not report.web_searched
        assert report.web_queries == 0
        fetch.assert_not_called()
        submission.refresh_from_db()
        payload = report_payload(submission, submission.user)
        assert payload["web_status"] == "failed" and payload["web_searched"] is False

    @override_settings(PLAGIARISM_WEB_ENABLED=True)
    @patch("plagiarism.web.fetch_text", return_value="")
    @patch("plagiarism.web.lookup", return_value=([Hit("https://example.org/essay", "Essay site", "")], True))
    def test_pages_that_could_not_be_opened_mean_the_search_failed(self, _lookup, _fetch, _embed):
        report = run_check(_text_submission(UserFactory(), ESSAY, personal=True))
        assert report.web_status == PlagiarismReport.WebStatus.FAILED
        assert not report.web_searched

    @override_settings(PLAGIARISM_WEB_ENABLED=True)
    @patch("plagiarism.web.lookup", return_value=([], True))
    def test_text_too_short_for_a_web_search(self, lookup, _embed):
        report = run_check(_text_submission(UserFactory(), "Коротко и ясно: да.", personal=True))
        lookup.assert_not_called()
        assert report.web_status == PlagiarismReport.WebStatus.SHORT
        assert not report.web_searched


def _org_class(web_search_enabled):
    owner = UserFactory()
    org = Organization.create_for(owner, "Lyceum", f"lyceum-{owner.id}")
    org.web_search_enabled = web_search_enabled
    org.save(update_fields=["web_search_enabled"])
    return Classroom.create_for(owner, "9A", organization=org)


@pytest.mark.django_db
@patch("plagiarism.service.embed", side_effect=fake_embed)
@patch("plagiarism.web.fetch_text", return_value="A page about something else, with no shared sentences at all.")
@patch("plagiarism.web.lookup", return_value=([Hit("https://example.org/essay", "Essay site", "")], True))
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
        assert report.web_status == PlagiarismReport.WebStatus.OFF

    def test_org_class_work_is_searched_when_the_school_allows_it(self, search, _fetch, _embed):
        report = run_check(_text_submission(UserFactory(), ESSAY, _org_class(True)))
        assert search.called
        assert report.web_searched
        assert report.web_status == PlagiarismReport.WebStatus.OK
        assert report.matches == []

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
        a, b = UserFactory(first_name="Анна", last_name="Смирнова"), UserFactory()
        for s in (a, b):
            Membership.objects.create(classroom=classroom, user=s)
        source = _text_submission(a, ESSAY, classroom)
        run_check(source)
        copy = _text_submission(b, ESSAY, classroom)
        run_check(copy)
        copy.refresh_from_db()
        teacher_view = report_payload(copy, teacher)["matches"][0]
        assert teacher_view["author"] == "Анна Смирнова"
        assert teacher_view["excerpts"]
        assert teacher_view["source_excerpts"] == teacher_view["excerpts"]
        assert teacher_view["hidden"] is False
        student_view = report_payload(copy, b)["matches"][0]
        assert student_view["title"] is None
        assert student_view["hidden"] is True
        assert student_view["hidden_reason"] == "student_view"
        assert "author" not in student_view and "submission_id" not in student_view
        assert student_view["excerpts"]
        assert student_view["source_excerpts"] == [""] * len(student_view["excerpts"])

    def test_teacher_of_another_class_sees_a_hidden_source(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY, _class()))
        teacher = UserFactory()
        classroom = Classroom.create_for(teacher, "9B", level=9)
        copy = _text_submission(UserFactory(), ESSAY, classroom)
        run_check(copy)
        copy.refresh_from_db()
        row = report_payload(copy, teacher)["matches"][0]
        assert row["hidden"] is True and row["title"] is None
        assert row["hidden_reason"] == "other_class"

    def test_personal_check_by_the_author_hides_the_class_source_plainly(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY))
        mine = _text_submission(UserFactory(), ESSAY, personal=True)
        run_check(mine)
        mine.refresh_from_db()
        row = report_payload(mine, mine.user)["matches"][0]
        assert row["hidden"] is True and row["hidden_reason"] == "student_view"

    def test_teacher_checking_a_text_alone_is_told_the_source_class_is_not_theirs(self, _embed):
        run_check(_text_submission(UserFactory(), ESSAY))
        teacher = UserFactory()
        Classroom.create_for(teacher, "7B", level=7)
        mine = _text_submission(teacher, ESSAY, personal=True)
        run_check(mine)
        mine.refresh_from_db()
        row = report_payload(mine, teacher)["matches"][0]
        assert row["hidden"] is True and row["hidden_reason"] == "other_class"


@pytest.mark.django_db
class TestPayload:
    def _done(self, text, matches, originality, matched, total):
        submission = _text_submission(UserFactory(), text, personal=True)
        TextFingerprint.objects.create(submission=submission, text=text, fingerprints=[], in_repository=False)
        PlagiarismReport.objects.create(
            submission=submission, status=PlagiarismReport.Status.DONE, originality=originality,
            matched_chars=matched, total_chars=total, matches=matches,
        )
        submission.refresh_from_db()
        return submission

    def test_excerpts_are_the_longest_passages_in_text_order(self):
        parts = ["аа", "бббббббббб", "ввв", "гггггггг", "дддддддддддд", "е", "жжжжжжж"]
        text = " ".join(parts)
        pairs = []
        start = 0
        for part in parts:
            pairs.append({"own": [start, start + len(part)], "text": part.upper(), "kind": "exact"})
            start += len(part) + 1
        match = {
            "source": "web", "kind": "exact", "url": "https://example.org", "title": "Site",
            "spans": [p["own"] for p in pairs], "pairs": pairs, "matched_chars": 40,
        }
        submission = self._done(text, [match], 0.0, 40, 40)
        row = report_payload(submission, submission.user)["matches"][0]
        assert row["excerpts"] == ["бббббббббб", "ввв", "гггггггг", "дддддддддддд", "жжжжжжж"]
        assert row["source_excerpts"] == [e.upper() for e in row["excerpts"]]

    def test_share_of_an_old_report_never_goes_above_the_total(self):
        match = {**WEB_MATCH, "matched_chars": 1209}
        submission = self._done(OWN, [match], 0.0, 1000, 1000)
        payload = report_payload(submission, submission.user)
        assert payload["matches"][0]["share"] == 100.0
        assert payload["matches"][0]["source_excerpts"] == [""]
        assert payload["web_status"] == "off"

    def test_source_share_is_not_above_the_headline(self):
        match = {**WEB_MATCH, "matched_chars": 389}
        submission = self._done(OWN, [match], 61.2, 389, 1000)
        assert report_payload(submission, submission.user)["matches"][0]["share"] == 38.9
        overcounted = {**match, "matched_chars": 392}
        submission = self._done(OWN, [overcounted], 61.2, 392, 1000)
        assert report_payload(submission, submission.user)["matches"][0]["share"] == 39.0


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
