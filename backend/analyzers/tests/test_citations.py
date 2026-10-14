from unittest import mock

import pytest

from analyzers.aggregator import aggregate
from analyzers.implementations.text_signals import TextCitationsAnalyzer
from analyzers.models import AnalysisResult
from analyzers.text import citations
from analyzers.text.citation_style import check_format, detect_style, entry_issues
from analyzers.text.citations import (
    FOUND,
    MISSING,
    UNCHECKED,
    CitationReport,
    Reference,
    check_bibliography,
    check_doi,
    check_isbn,
    check_url,
    extract,
    isbn_valid,
    title_matches,
)
from common.url_safety import UnsafeUrlError
from content.tests.factories import SubmissionFactory

from .factories import AnalysisResultFactory, AnalyzerConfigFactory

PAPER = (
    "Sleep affects memory consolidation (Walker, 2017). A meta-analysis confirmed it, doi:10.1038/nature12345. "
    "See also arXiv:2301.01234v2 and the book ISBN 978-0-306-40615-7. Data: https://example.org/sleep-study.\n\n"
    "As the author wrote, «the brain uses sleep to sort the memories of the day into the ones worth keeping».\n\n"
    "References\n"
    "Walker, M. (2017). Why We Sleep: Unlocking the Power of Sleep and Dreams. Scribner.\n"
    "Short line 2019\n"
)


def response(status=200, payload=None, text=""):
    resp = mock.Mock(status_code=status, text=text)
    resp.json.return_value = payload or {}
    return resp


STYLE_SAMPLES = {
    "apa": "Walker, M. P., & Stickgold, R. (2006). Sleep, memory, and plasticity. Annual Review of Psychology, 57, 139–166. https://doi.org/10.1146/annurev.psych.56.091103.070307",
    "mla": 'Walker, Matthew. "Sleep and Memory." Annual Review of Psychology, vol. 57, no. 1, 2006, pp. 139-66.',
    "chicago": "Walker, Matthew. 2017. Why We Sleep: Unlocking the Power of Sleep and Dreams. New York: Scribner.",
    "harvard": "Walker, M. (2017) Why we sleep. London: Penguin. Available at: https://example.org/book (Accessed: 1 May 2024).",
    "ieee": '[1] M. P. Walker and R. Stickgold, "Sleep, memory, and plasticity," Annu. Rev. Psychol., vol. 57, no. 1, pp. 139–166, 2006.',
    "vancouver": "1. Walker MP, Stickgold R. Sleep, memory, and plasticity. Annu Rev Psychol. 2006;57:139-66.",
    "gost": "Иванов, И. И. Психология сна : учебное пособие / И. И. Иванов. – Москва : Наука, 2019. – 256 с.",
    "iso690": "DUPONT, Jean. Le sommeil et la mémoire. Paris : Gallimard, 2015. 320 p.",
}


class TestExtract:
    def test_finds_every_kind(self):
        refs = {(r.kind, r.value) for r in extract(PAPER)}
        assert ("doi", "10.1038/nature12345") in refs
        assert ("arxiv", "2301.01234") in refs
        assert ("isbn", "9780306406157") in refs
        assert ("url", "https://example.org/sleep-study") in refs
        assert any(kind == "bibliography" and value.startswith("Walker, M. (2017)") for kind, value in refs)
        assert any(kind == "quote" and value.startswith("the brain uses sleep") for kind, value in refs)

    def test_short_bibliography_lines_and_doi_links_are_not_double_counted(self):
        refs = extract("Read https://doi.org/10.1000/xyz123 now.\n\nReferences\nShort line 2019")
        assert [(r.kind, r.value) for r in refs] == [("doi", "10.1000/xyz123")]

    def test_bad_isbn_checksum_is_missing_without_a_lookup(self):
        ref = extract("ISBN 978-0-306-40615-8")[0]
        assert (ref.kind, ref.status) == ("isbn", MISSING)

    def test_isbn_checksums(self):
        assert isbn_valid("0306406152") and isbn_valid("9780306406157") and isbn_valid("080442957X")
        assert not isbn_valid("0306406153") and not isbn_valid("12345")

    def test_text_without_sources(self):
        assert extract("I went to the river with my brother and we caught a big fish.") == []


class TestChecks:
    def test_doi_handle_lookup(self):
        ref = Reference("doi", "10.1038/nature12345")
        with mock.patch.object(citations.requests, "get", return_value=response(404, {"responseCode": 100})):
            check_doi(ref)
        assert ref.status == MISSING
        ref = Reference("doi", "10.1038/nature14539")
        with mock.patch.object(citations.requests, "get", return_value=response(200, {"responseCode": 1})):
            check_doi(ref)
        assert ref.status == FOUND

    def test_doi_server_error_stays_unchecked(self):
        ref = Reference("doi", "10.1/x")
        with mock.patch.object(citations.requests, "get", return_value=response(503)):
            check_doi(ref)
        assert ref.status == UNCHECKED

    def test_isbn_falls_back_to_google_books(self):
        ref = Reference("isbn", "9780306406157")
        replies = [response(404), response(200, {"items": [{"volumeInfo": {"title": "Pathways"}}]})]
        with mock.patch.object(citations.requests, "get", side_effect=replies):
            check_isbn(ref)
        assert (ref.status, ref.detail) == (FOUND, "Pathways")
        ref = Reference("isbn", "9780306406157")
        with mock.patch.object(citations.requests, "get", side_effect=[response(404), response(200, {"totalItems": 0})]):
            check_isbn(ref)
        assert ref.status == MISSING

    def test_url_statuses(self):
        ref = Reference("url", "https://example.org/a")
        with mock.patch.object(citations, "safe_get", return_value=response(404)):
            check_url(ref)
        assert ref.status == MISSING
        ref = Reference("url", "https://example.org/b")
        with mock.patch.object(citations, "safe_get", return_value=response(403)):
            check_url(ref)
        assert ref.status == UNCHECKED
        ref = Reference("url", "https://no-such-host.example/c")
        with mock.patch.object(citations, "safe_get", side_effect=UnsafeUrlError("Invalid URL")):
            check_url(ref)
        assert ref.status == MISSING

    def test_private_url_is_never_fetched_or_blamed(self):
        ref = Reference("url", "http://10.0.0.1/admin")
        with mock.patch.object(citations, "safe_get", side_effect=UnsafeUrlError("URL not allowed")):
            check_url(ref)
        assert ref.status == UNCHECKED

    def test_bibliography_matches_title(self):
        entry = "Walker, M. (2017). Why We Sleep: Unlocking the Power of Sleep and Dreams. Scribner."
        ref = Reference("bibliography", entry)
        hit = response(200, {"results": [{"title": "Why We Sleep: Unlocking the Power of Sleep and Dreams"}]})
        with mock.patch.object(citations.requests, "get", return_value=hit):
            check_bibliography(ref)
        assert ref.status == FOUND
        ref = Reference("bibliography", "Ivanova, A. (2021). Quantum gardening for teenagers. Moscow Press.")
        empty = [response(200, {"results": [{"title": "Unrelated work on soil"}]}), response(200, {"message": {"items": []}})]
        with mock.patch.object(citations.requests, "get", side_effect=empty):
            check_bibliography(ref)
        assert ref.status == MISSING

    def test_title_match_needs_most_words(self):
        assert title_matches("Why We Sleep", "Walker. Why we sleep. 2017")
        assert not title_matches("Why We Sleep Better at Night", "Walker. Why we sleep. 2017")
        assert not title_matches("On", "On sleep")


class TestReport:
    def test_two_invented_ids_flag(self):
        report = CitationReport([Reference("doi", "a", MISSING), Reference("isbn", "b", MISSING), Reference("url", "c", FOUND)])
        assert report.flagged and 0.6 <= report.confidence() <= 0.95

    def test_one_dead_link_among_found_sources_does_not_flag(self):
        report = CitationReport([Reference("url", "a", MISSING), Reference("doi", "b", FOUND), Reference("doi", "c", FOUND)])
        assert not report.flagged

    def test_unchecked_sources_do_not_count(self):
        report = CitationReport([Reference("doi", "a", UNCHECKED), Reference("url", "b", UNCHECKED)])
        assert report.checked_weight == 0 and not report.flagged


class TestFormat:
    @pytest.mark.parametrize("style", sorted(STYLE_SAMPLES))
    def test_clean_entries_are_recognised_without_issues(self, style):
        entry = STYLE_SAMPLES[style]
        assert detect_style(entry) == style
        assert entry_issues(entry, style) == []

    def test_gost_mistakes(self):
        entry = "Иванов И.И. Психология сна. - М.: Наука, 2019. - 256 стр"
        issues = entry_issues(entry, detect_style(entry))
        assert len(issues) == 4
        assert any("дефисом" in i for i in issues) and any("Иванов, И. И." in i for i in issues)

    def test_gost_web_source_needs_url_and_access_date(self):
        issues = entry_issues("Петров, П. П. Сон и память. – Москва, 2020. – https://nkj.ru/sleep.", "gost")
        assert "перед адресом пишется URL:" in issues
        assert "после адреса нужна (дата обращения: ДД.ММ.ГГГГ)" in issues

    def test_apa_mistakes(self):
        issues = entry_issues("Walker, M. and Stickgold, R. (2006). Sleep and memory. Retrieved from https://x.org doi:10.1/abc", "apa")
        assert "use & before the last author, not 'and'" in issues
        assert "APA 7 drops 'Retrieved from' before a link" in issues
        assert "write the DOI as https://doi.org/10..." in issues

    def test_vancouver_initials_with_periods(self):
        assert "write initials without periods: Smith JA" in entry_issues(
            "1. Walker M.P., Stickgold R. Sleep and plasticity. Annu Rev Psychol. 2006;57:139-66.", "vancouver"
        )

    def test_list_level_problems(self):
        text = (
            "Sleep matters (Walker, 2017) and (Smith, 2020) agree.\n\nReferences\n"
            + STYLE_SAMPLES["apa"]
            + "\nAdams, J. (2019). Dreams and the brain explained. Oxford University Press.\n"
            + STYLE_SAMPLES["mla"]
        )
        report = check_format(text)
        assert report["style"] == "apa" and report["label"] == "APA 7"
        assert "1 of 3 entries follow MLA 9 while the list is mostly APA 7" in report["issues"]
        assert "the list is not in alphabetical order by author" in report["issues"]
        assert "cited in the text but missing from the list: Smith" in report["issues"]

    def test_numbered_citation_beyond_list(self):
        text = "As shown in [1] and [4].\n\nReferences\n" + STYLE_SAMPLES["ieee"]
        report = check_format(text)
        assert report["style"] == "ieee"
        assert "numbered citations with no matching entry: [4]" in report["issues"]

    def test_no_reference_list(self):
        assert check_format("Just an essay without sources, written in 2020 by me.") is None


@pytest.mark.django_db
class TestAnalyzer:
    def _run(self, tmp_path, text, refs):
        path = tmp_path / "essay.txt"
        path.write_text(text)
        with mock.patch("analyzers.implementations.text_signals.check_citations", return_value=CitationReport(refs)):
            return TextCitationsAnalyzer().analyze(str(path), {"mime_type": "text/plain"})

    def test_invented_sources_are_a_context_flag(self, tmp_path):
        out = self._run(tmp_path, PAPER, [Reference("doi", "a", MISSING), Reference("arxiv", "b", MISSING)])
        assert out.verdict == "suspicious" and out.confidence >= 0.6
        assert out.evidence["context_signal"] and out.evidence["counts"][MISSING] == 2

    def test_real_sources(self, tmp_path):
        out = self._run(tmp_path, PAPER, [Reference("doi", "a", FOUND)])
        assert out.verdict == "inconclusive" and out.evidence["finding"] == "cited sources check out"
        assert out.evidence["format"]["style"] is not None

    def test_nothing_to_check(self, tmp_path):
        out = self._run(tmp_path, "plain essay", [])
        assert out.verdict == "inconclusive" and out.confidence == 0.0

    def test_flag_sends_to_review_but_never_convicts(self):
        sub = SubmissionFactory()
        results = [
            AnalysisResultFactory(
                submission=sub,
                analyzer=AnalyzerConfigFactory(name="text_classifier", weight=2.5),
                verdict=AnalysisResult.Verdict.AUTHENTIC,
                confidence=0.8,
                evidence={"ai_probability": 0.1},
            ),
            AnalysisResultFactory(
                submission=sub,
                analyzer=AnalyzerConfigFactory(name="text_citations", weight=1.0),
                verdict=AnalysisResult.Verdict.SUSPICIOUS,
                confidence=0.9,
                evidence={},
            ),
        ]
        assert aggregate(results)[1] == "needs_review"
