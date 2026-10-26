import pytest

from analyzers.tests.factories import AnalysisResultFactory, AnalyzerConfigFactory
from classroom.models import Classroom, Membership
from content.pdf import _originality, build_report_context
from content.tests.factories import SubmissionFactory
from provenance.models import ProvenanceResult
from factcheck.pdf import build_factcheck_context
from plagiarism.models import PlagiarismReport
from reports.copy import field_name, kind_name, tone_set
from reports.render import HTML, render_html, render_pdf
from users.tests.factories import UserFactory


def _vote(submission, name, verdict, confidence, evidence=None):
    AnalysisResultFactory(
        submission=submission, analyzer=AnalyzerConfigFactory(name=name), verdict=verdict, confidence=confidence,
        evidence=evidence or {},
    )


def _class_work(verdict="needs_review", mime="text/plain"):
    teacher = UserFactory(language="ru", first_name="Анна", last_name="Петрова")
    classroom = Classroom.create_for(teacher, "9Б")
    student = UserFactory(language="ru", first_name="Ольга", last_name="Смирнова")
    Membership.objects.create(classroom=classroom, user=student)
    work = SubmissionFactory(
        user=student, classroom=classroom, final_verdict=verdict, final_score=0.6, mime_type=mime, status="completed",
    )
    return teacher, student, work


@pytest.mark.django_db
class TestClassReport:
    def _text_votes(self, work):
        _vote(work, "text_classifier", "suspicious", 0.7, {"ai_probability": 0.71})
        _vote(work, "text_evasion", "authentic", 0.9)
        _vote(work, "text_shadow", "inconclusive", 0.0, {"reason": "no shadow set"})

    def test_teacher_report_speaks_like_the_result_page(self):
        teacher, _student, work = _class_work()
        self._text_votes(work)
        context = build_report_context(work, teacher)
        assert context["badge"] == "Итог"
        assert context["headline"] == "Стоит присмотреться"
        assert context["meaning"].startswith("На что обратить внимание: похоже на текст чат-бота")
        assert context["next_step"].startswith("Что делать:")
        assert [c["title"] for c in context["checks"]] == ["Текст от ИИ", "Скрытые уловки", "ИИ-ответы на задание"]
        assert context["members"] == []
        assert context["details"][0] == [("Ученик", "Ольга Смирнова"), ("Класс", "9Б"), ("Сдана", context["details"][0][2][1])]
        assert context["details"][1][2] == ("Размер", "1,0 КБ")
        assert "score_pct" not in context

    def test_student_report_uses_student_wording(self):
        _teacher, student, work = _class_work()
        self._text_votes(work)
        context = build_report_context(work, student)
        assert context["headline"] == "Учитель может задать вопросы по этой работе"
        assert context["next_step"] == ""
        assert "ИИ-ответы на задание" not in [c["title"] for c in context["checks"]]

    def _copied(self, work, matches, originality):
        PlagiarismReport.objects.create(
            submission=work, status=PlagiarismReport.Status.DONE, originality=originality, total_chars=1000,
            matched_chars=sum(m["matched_chars"] for m in matches), matches=matches,
        )

    def test_headline_names_the_main_source_of_copied_work(self):
        teacher, student, work = _class_work(verdict="inconclusive")
        self._copied(work, [{
            "source": "web", "kind": "exact", "url": "https://ru.wikipedia.org/wiki/x", "title": "Наташа Ростова",
            "matched_chars": 700, "spans": [[0, 700]],
        }], 30.0)
        assert build_report_context(work, teacher)["headline"] == "Большая часть текста найдена в источнике: Наташа Ростова (ru.wikipedia.org)"
        assert build_report_context(work, student)["headline"] == "Большая часть текста найдена в других источниках"

    def test_headline_names_the_biggest_of_several_sources(self):
        teacher, _student, work = _class_work(verdict="inconclusive")
        self._copied(work, [
            {"source": "web", "kind": "exact", "url": "https://ru.wikipedia.org/wiki/x", "title": "Наташа Ростова", "matched_chars": 400, "spans": [[0, 400]]},
            {"source": "web", "kind": "exact", "url": "https://example.org/y", "title": "Сочинение", "matched_chars": 250, "spans": [[400, 650]]},
        ], 35.0)
        assert build_report_context(work, teacher)["headline"] == (
            "Большая часть текста найдена в других источниках, главный из них: Наташа Ростова (ru.wikipedia.org)"
        )

    def test_class_link_points_to_classroom(self, settings):
        settings.CLASSROOM_URL = "https://classroom.example"
        teacher, _student, work = _class_work()
        assert build_report_context(work, teacher)["result_url"] == f"https://classroom.example/results/{work.id}"

    def test_watermark_proof_is_named_instead_of_detector_agreement(self):
        teacher, _student, work = _class_work(verdict="fake", mime="image/png")
        _vote(work, "metadata", "fake", 0.98, {
            "provenance_proof": True,
            "ai_trace": [{"kind": "watermark", "ai": "generated", "generator": "FLUX.1", "signed_by": "Black Forest Labs", "match": 1.0, "damaged": False}],
        })
        _vote(work, "community_forensics", "authentic", 0.8)
        context = build_report_context(work, teacher)
        assert context["meaning"].startswith("Создано нейросетью: в файле есть её невидимая метка (FLUX.1)")
        assert context["note"] == "Метку ставит сама нейросеть. Что делать с работой, решает учитель."
        assert context["detector_line"] == ""
        assert context["next_step"].startswith("Что делать: обсудите с учеником")
        assert context["show_traces"] is True
        assert "FLUX.1" in context["traces"][0]
        assert context["headline"] == "Создано нейросетью: это доказывает метка в файле"

    def test_picture_headline_does_not_talk_about_writing(self):
        teacher, student, work = _class_work(verdict="likely_fake", mime="image/jpeg")
        _vote(work, "custom_detector", "fake", 0.9)
        _vote(work, "community_forensics", "fake", 0.9)
        assert build_report_context(work, teacher)["headline"] == "Серьёзные признаки, что картинку сделала нейросеть"
        assert build_report_context(work, student)["headline"] == "Учитель захочет обсудить эту работу"

    def test_teacher_own_earlier_picture_is_not_called_handed_in(self):
        teacher, student, work = _class_work(verdict="suspicious", mime="image/png")
        earlier = SubmissionFactory(user=teacher, original_filename="sample.png")
        ProvenanceResult.objects.create(
            submission=work,
            source_type=ProvenanceResult.SourceType.PHASH_MATCH,
            similarity_score=1.0,
            raw_data={"submission_id": str(earlier.id), "distance": 0},
        )
        line = build_report_context(work, teacher)["provenance"][0]["title"]
        assert line.startswith("Такую же картинку вы уже проверяли: sample.png")
        mine = SubmissionFactory(user=student, classroom=work.classroom, original_filename="draft.png")
        ProvenanceResult.objects.create(
            submission=work,
            source_type=ProvenanceResult.SourceType.PHASH_MATCH,
            similarity_score=1.0,
            raw_data={"submission_id": str(mine.id), "distance": 0},
        )
        lines = [p["title"] for p in build_report_context(work, student)["provenance"]]
        assert any(line.startswith("Такую же картинку вы уже сдавали: draft.png, 9Б") for line in lines)

    def test_single_detector_is_not_called_agreement(self):
        user = UserFactory(language="ru")
        work = SubmissionFactory(user=user, final_verdict="fake", final_score=0.8, mime_type="image/jpeg")
        _vote(work, "custom_detector", "fake", 0.9)
        _vote(work, "community_forensics", "inconclusive", 0.5)
        context = build_report_context(work, user)
        assert "независимые детекторы" not in context["meaning"]
        assert context["meaning"].startswith("Один детектор уверен")
        assert context["detector_line"] == "Детекторы нейросетей: за нейросеть 1 из 2."

    def test_software_trace_shows_the_field_and_value(self):
        teacher, _student, work = _class_work(verdict="fake", mime="image/png")
        _vote(work, "metadata", "fake", 0.9, {
            "ai_trace": [{"kind": "software_tag", "ai": "generated", "generator": "midjourney", "field": "xmp:CreatorTool", "raw_value": "Midjourney v6"}],
        })
        assert build_report_context(work, teacher)["traces"] == ["В поле «Программа» файла записано: «Midjourney v6»."]

    def test_template_renders_without_scores(self):
        teacher, _student, work = _class_work()
        self._text_votes(work)
        html = render_html("content/report.html", build_report_context(work, teacher))
        assert "Стоит присмотреться" in html
        assert "вероятность ИИ" not in html


def test_hidden_internal_source_is_named_in_the_report_language():
    payload = {
        "status": "done", "originality": 70, "matched_chars": 30, "total_chars": 100, "web_searched": False,
        "matches": [
            {"source": "internal", "title": "Another ProofLayer submission", "share": 20},
            {"source": "internal", "title": None, "hidden": True, "share": 5},
            {"source": "internal", "submission_id": "x", "author": "Полина Новикова", "classroom": "9Б", "title": "essay.docx", "share": 5},
        ],
    }
    titles = [s["title"] for s in _originality(payload, "ru")["sources"]]
    assert titles == ["Работа, сданная раньше в ProofLayer", "Работа, сданная раньше в ProofLayer", "Работа: Полина Новикова, 9Б"]


def test_paper_source_names_authors_year_and_venue_and_the_scope_names_the_engines():
    paper = {
        "source": "web", "engine": "openalex", "url": "https://doi.org/10.1/x", "title": "Winnowing", "share": 40,
        "authors": ["S. Schleimer", "D. Wilkerson", "A. Aiken"], "authors_total": 4, "year": 2003, "venue": "SIGMOD",
    }
    wiki = {"source": "web", "engine": "wikipedia", "url": "https://ru.wikipedia.org/wiki/X", "title": "X", "share": 5}
    payload = {
        "status": "done", "originality": 55, "matched_chars": 45, "total_chars": 100, "web_searched": True,
        "web_engines": ["arxiv", "openalex", "wikipedia"], "matches": [paper, wiki],
    }
    ru = _originality(payload, "ru")
    assert [s["title"] for s in ru["sources"]] == ["Winnowing (S. Schleimer, D. Wilkerson, A. Aiken и др., 2003, SIGMOD)", "X"]
    assert ru["scope"] == "Также сравнено: Википедия, открытые научные статьи (OpenAlex, arXiv)"
    en = _originality({**payload, "web_engines": ["web"]}, "en")
    assert en["scope"] == "Also compared with a web search"
    arxiv_only = _originality({**payload, "web_engines": ["arxiv", "web", "wikipedia"]}, "en")
    assert arxiv_only["scope"] == "Also compared with Wikipedia, open scientific papers (arXiv), a web search"
    assert _originality({**payload, "web_engines": []}, "en")["scope"] == "Web search included"


def test_field_names_are_plain():
    assert field_name("png_text.parameters", "ru") == "Настройки генерации"
    assert field_name("Software", "ru") == "Программа"
    assert field_name("photoshop:Credit", "en") == "Credit line"


@pytest.mark.django_db
class TestSubmissionReport:
    def test_russian_context_uses_human_names_and_drops_errors(self):
        user = UserFactory(language="ru")
        submission = SubmissionFactory(user=user, final_verdict="likely_fake", final_score=0.87, mime_type="image/jpeg")
        _vote(submission, "custom_detector", "fake", 0.94)
        _vote(submission, "ela", "authentic", 0.6)
        _vote(submission, "llm_vision", "inconclusive", 0.0)
        _vote(submission, "metadata", "error", 0.0)
        context = build_report_context(submission, user)
        assert context["lang"] == "ru"
        assert context["headline"] == "Вероятно, создано нейросетью"
        assert "score_pct" not in context
        names = [m["name"] for m in context["members"]]
        assert names == ["Детектор ProofLayer", "Проверка монтажа", "Модель, которая смотрит на картинку"]
        assert [m["vote"] for m in context["members"]] == ["за нейросеть", "за фото", "не уверен"]
        assert all("pct" not in m for m in context["members"])
        assert context["result_url"].endswith(f"/results/{submission.id}")
        flat = [cell[0] for row in context["details"] for cell in row]
        assert "Статус" not in flat and "MIME" not in " ".join(flat) and "SHA-256" not in flat
        assert context["technical"].startswith("SHA-256")

    def test_passages_pick_the_most_machine_like_segments(self):
        submission = SubmissionFactory(final_verdict="needs_review", final_score=0.6, mime_type="text/plain")
        AnalysisResultFactory(
            submission=submission,
            analyzer=AnalyzerConfigFactory(name="text_classifier"),
            verdict="suspicious",
            confidence=0.5,
            evidence={"segments": [
                {"excerpt": "a", "text": "human part", "ai_probability": 0.1},
                {"excerpt": "b", "text": "machine part", "ai_probability": 0.92},
                {"excerpt": "c", "text": "mixed part", "ai_probability": 0.5},
            ]},
        )
        passages = build_report_context(submission, None)["passages"]
        assert [p["text"] for p in passages] == ["machine part", "mixed part"]
        assert passages[0]["pct"] == 92

    def test_english_is_default_and_unknown_verdict_is_readable(self):
        submission = SubmissionFactory(final_verdict="", final_score=None)
        context = build_report_context(submission, None)
        assert context["lang"] == "en"
        assert context["headline"] == "Inconclusive"
        assert "score_pct" not in context


def test_factcheck_context_localizes_and_collects_sources():
    result = {
        "overall_verdict": "misleading",
        "claims": [{"claim": "A", "assessment": "likely_false", "confidence": 0.8, "wikipedia": {"title": "A", "url": "https://w/a"}, "sources": [{"url": "https://s/1"}]}],
        "entities": [{"text": "Paris"}, {"text": "Paris"}],
    }
    context = build_factcheck_context(result, "text", "ru")
    assert context["headline"] == "Вводит в заблуждение"
    assert context["claims"][0]["confidence"] == 80
    assert [s["url"] for s in context["claims"][0]["sources"]] == ["https://w/a", "https://s/1"]
    assert context["entities"] == ["Paris"]


def test_kind_and_tone_helpers():
    assert kind_name("image/jpeg", "en") == "Picture · JPEG"
    assert kind_name("image/png", "ru") == "Картинка · PNG"
    assert kind_name("text/plain", "ru") == "Текст"
    assert kind_name("video/quicktime", "ru") == "Видео · MOV"
    assert kind_name("audio/x-wav", "en") == "Audio · WAV"
    assert kind_name("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "ru") == "Документ · DOCX"
    assert tone_set("blood")["tone_line"] == "rgba(255,87,115,0.4)"


@pytest.mark.skipif(HTML is None, reason="WeasyPrint system libraries are not installed")
def test_factcheck_pdf_renders():
    pdf = render_pdf("factcheck/report.html", build_factcheck_context({"overall_verdict": "no_claims", "claims": []}, "", "en"))
    assert pdf.startswith(b"%PDF")
