import pytest
from unittest.mock import patch, MagicMock

from factcheck.services import (
    _fallback_sentence_split,
    analyze_text,
    check_google_fact_check,
    search_web,
)


class TestFallbackSentenceSplit:
    def test_splits_on_period(self):
        text = "The president announced major economic reforms yesterday. The stock market responded with significant gains across all sectors."
        result = _fallback_sentence_split(text)
        assert len(result) >= 2
        assert all(isinstance(s["claim"], str) for s in result)
        assert all(s["assessment"] == "uncertain" for s in result)

    def test_empty_text_returns_empty(self):
        assert _fallback_sentence_split("") == []

    def test_short_sentences_excluded(self):
        result = _fallback_sentence_split("Hi. Hello. The quick brown fox jumped over the lazy dog and kept running.")
        claims = [s["claim"] for s in result]
        assert all(len(c) > 20 for c in claims)

    def test_max_8_results(self):
        text = ". ".join([f"Sentence number {i} contains verifiable claim about something" for i in range(20)])
        result = _fallback_sentence_split(text)
        assert len(result) <= 8


class TestCheckGoogleFactCheckNoKey:
    def test_no_api_key_returns_empty(self):
        with patch("factcheck.services.settings") as mock_settings:
            mock_settings.GOOGLE_FACT_CHECK_KEY = None
            result = check_google_fact_check("some claim text")
        assert result == []


class TestSearchWeb:
    def test_ddgs_exception_returns_empty(self):
        with patch("duckduckgo_search.DDGS") as mock_ddgs:
            mock_ddgs.side_effect = Exception("network error")
            result = search_web("test query")
        assert result == ""

    def test_returns_joined_snippets(self):
        fake_results = [
            {"title": "Title A", "body": "Body A", "href": "http://a.com"},
            {"title": "Title B", "body": "Body B", "href": "http://b.com"},
        ]
        with patch("duckduckgo_search.DDGS") as mock_ddgs:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=ctx)
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.text = MagicMock(return_value=fake_results)
            mock_ddgs.return_value = ctx
            result = search_web("some query")
        assert "Title A" in result
        assert "Title B" in result


class TestAnalyzeText:
    @patch("factcheck.services.check_google_fact_check", return_value=[])
    @patch("factcheck.services.extract_entities", return_value=[])
    @patch("factcheck.services.analyze_with_ollama")
    def test_mostly_accurate_verdict(self, mock_ollama, mock_entities, mock_fc):
        mock_ollama.return_value = [
            {"claim": "Paris is in France.", "assessment": "likely_true", "explanation": "yes"},
            {"claim": "Water boils at 100C.", "assessment": "likely_true", "explanation": "yes"},
        ]
        result = analyze_text("Paris is in France. Water boils at 100C.")
        assert result["overall_verdict"] == "mostly_accurate"
        assert result["claims_count"] == 2

    @patch("factcheck.services.check_google_fact_check", return_value=[])
    @patch("factcheck.services.extract_entities", return_value=[])
    @patch("factcheck.services.analyze_with_ollama")
    def test_misleading_verdict_when_many_false(self, mock_ollama, mock_entities, mock_fc):
        mock_ollama.return_value = [
            {"claim": "claim 1", "assessment": "likely_false", "explanation": "x"},
            {"claim": "claim 2", "assessment": "likely_false", "explanation": "x"},
            {"claim": "claim 3", "assessment": "likely_false", "explanation": "x"},
        ]
        result = analyze_text("some text with false claims")
        assert result["overall_verdict"] == "misleading"

    @patch("factcheck.services.check_google_fact_check", return_value=[])
    @patch("factcheck.services.extract_entities", return_value=[])
    @patch("factcheck.services.analyze_with_ollama")
    def test_no_claims_verdict(self, mock_ollama, mock_entities, mock_fc):
        mock_ollama.return_value = []
        result = analyze_text("some text")
        assert result["overall_verdict"] == "no_claims"
        assert result["claims_count"] == 0

    @patch("factcheck.services.check_google_fact_check", return_value=[])
    @patch("factcheck.services.extract_entities", return_value=[])
    @patch("factcheck.services.analyze_with_ollama")
    def test_result_includes_fact_checks_field(self, mock_ollama, mock_entities, mock_fc):
        mock_ollama.return_value = [
            {"claim": "Some claim.", "assessment": "uncertain", "explanation": "unclear"},
        ]
        result = analyze_text("Some claim.")
        assert "fact_checks" in result["claims"][0]

    @patch("factcheck.services.check_google_fact_check", return_value=[])
    @patch("factcheck.services.extract_entities", return_value=[])
    @patch("factcheck.services.analyze_with_ollama")
    def test_mixed_verdict(self, mock_ollama, mock_entities, mock_fc):
        mock_ollama.return_value = [
            {"claim": "claim 1", "assessment": "likely_false", "explanation": "x"},
            {"claim": "claim 2", "assessment": "uncertain", "explanation": "x"},
            {"claim": "claim 3", "assessment": "likely_true", "explanation": "x"},
        ]
        result = analyze_text("mixed text")
        assert result["overall_verdict"] in ("mixed", "misleading")
