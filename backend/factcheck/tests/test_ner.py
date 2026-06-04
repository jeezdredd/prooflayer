import pytest
from unittest.mock import patch

from factcheck.ner import extract_claim_sentences, extract_entities, _regex_split


class TestRegexSplit:
    def test_splits_sentences(self):
        text = "The company earned $5 billion last year. CEO John resigned in 2023. Markets fell 10%."
        result = _regex_split(text, 8)
        assert len(result) >= 2

    def test_respects_max_claims(self):
        text = ". ".join([f"Sentence {i} with enough words to pass the length filter" for i in range(20)])
        result = _regex_split(text, 5)
        assert len(result) <= 5

    def test_empty_text(self):
        assert _regex_split("", 8) == []


class TestExtractClaimSentences:
    def test_empty_text_returns_empty(self):
        result = extract_claim_sentences("")
        assert result == []

    def test_whitespace_only_returns_empty(self):
        result = extract_claim_sentences("   ")
        assert result == []

    def test_fallback_when_nlp_fails(self):
        with patch("factcheck.ner._get_nlp", return_value=None):
            text = "The president earned $2 million in 2022. Markets dropped by 15 percent."
            result = extract_claim_sentences(text, max_claims=8)
        assert isinstance(result, list)

    def test_max_claims_respected(self):
        text = ". ".join([
            f"Company {i} earned ${i * 100}M in 2024 fiscal year results"
            for i in range(20)
        ])
        result = extract_claim_sentences(text, max_claims=3)
        assert len(result) <= 3

    def test_returns_list_of_strings(self):
        result = extract_claim_sentences("Some text about facts and numbers.")
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)


class TestExtractEntities:
    def test_returns_empty_when_nlp_unavailable(self):
        with patch("factcheck.ner._get_nlp", return_value=None):
            result = extract_entities("Barack Obama visited Paris in 2023.")
        assert result == []

    def test_returns_list(self):
        result = extract_entities("Some text here.")
        assert isinstance(result, list)
