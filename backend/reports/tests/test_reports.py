import pytest

from analyzers.tests.factories import AnalysisResultFactory, AnalyzerConfigFactory
from content.pdf import build_report_context
from content.tests.factories import SubmissionFactory
from factcheck.pdf import build_factcheck_context
from reports.copy import kind_name, tone_set
from reports.render import HTML, render_pdf
from users.tests.factories import UserFactory


def _vote(submission, name, verdict, confidence):
    AnalysisResultFactory(submission=submission, analyzer=AnalyzerConfigFactory(name=name), verdict=verdict, confidence=confidence)


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
        assert context["headline"] == "Вероятно создано ИИ"
        assert context["score_pct"] == 87
        names = [m["name"] for m in context["members"]]
        assert names == ["Детектор ProofLayer", "Анализ уровня ошибок (ELA)", "Визуальная модель"]
        assert context["members"][-1]["pct"] is None
        assert context["result_url"].endswith(f"/results/{submission.id}")
        flat = [cell[0] for row in context["details"] for cell in row]
        assert "Статус" not in flat and "MIME" not in " ".join(flat)

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
        assert context["score_pct"] == 0


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
    assert kind_name("image/jpeg", "en") == "Image · JPEG"
    assert kind_name("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "ru") == "Документ · DOCX"
    assert tone_set("blood")["tone_line"] == "rgba(255,87,115,0.4)"


@pytest.mark.skipif(HTML is None, reason="WeasyPrint system libraries are not installed")
def test_factcheck_pdf_renders():
    pdf = render_pdf("factcheck/report.html", build_factcheck_context({"overall_verdict": "no_claims", "claims": []}, "", "en"))
    assert pdf.startswith(b"%PDF")
