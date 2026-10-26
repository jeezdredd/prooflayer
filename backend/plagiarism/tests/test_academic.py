import hashlib
import json
from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.test import override_settings

from common.documents import extract_pdf
from content.tests.factories import SubmissionFactory
from plagiarism.academic import (
    Paper,
    arxiv_lookup,
    arxiv_search,
    fetch_turn,
    key_phrase,
    openalex_lookup,
    openalex_search,
    or_groups,
    parse_arxiv,
    rebuild_abstract,
    wait_turn,
)
from plagiarism.models import PlagiarismReport
from plagiarism.search import Hit
from plagiarism.serializers import report_payload
from plagiarism.service import run_check
from plagiarism.web import fetch_text, paper_text
from users.tests.factories import UserFactory

PAPER_ESSAY = (
    "Winnowing selects a small subset of hashed substrings so that every sufficiently long shared passage is detected. "
    "The guarantee holds because each window of consecutive hashes contributes its minimum "
    "to the document fingerprint. "
    "Local algorithms of this kind make copy detection practical for very large collections of student assignments. "
    "Our own experiments with programming courses confirmed that renaming variables does not hide the copied structure."
)
ABSTRACT_SENTENCES = PAPER_ESSAY.split(". ")[:2]
RU_ESSAY = (
    "Цифровая трансформация высшего образования изменила представления преподавателей "
    "о самостоятельной работе студентов. "
    "Дистанционные технологии потребовали пересмотра традиционных подходов к организации промежуточной аттестации. "
    "Многие университеты внедрили электронные курсы, которые сопровождают очные занятия на протяжении всего семестра."
)
BIBLIOGRAPHY = (
    "\n\nReferences\n"
    "Schleimer S., Wilkerson D. S., Aiken A. Winnowing: local algorithms for document fingerprinting "
    "in proceedings of the international conference on management of data, 2003.\n"
)


def _vector(seed: str) -> list[float]:
    digest = hashlib.sha256(seed.encode()).digest()
    raw = [b - 128 for b in (digest * 12)[:384]]
    norm = sum(x * x for x in raw) ** 0.5
    return [x / norm for x in raw]


def _fake_embed(sentences):
    return [_vector(s) for s in sentences]


def _inverted(text: str) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for pos, word in enumerate(text.split()):
        index.setdefault(word, []).append(pos)
    return index


def _pdf(text: str) -> bytes:
    lines, line = [], ""
    for word in text.split():
        if len(line) + len(word) > 80:
            lines.append(line)
            line = ""
        line = f"{line} {word}".strip()
    lines.append(line)
    escaped = [ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for ln in lines]
    stream = "BT /F1 10 Tf 14 TL 40 760 Td " + " ".join(f"({ln}) Tj T*" for ln in escaped) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


class FakeResponse:
    def __init__(self, status=200, payload=None, content=b"", headers=None, content_type="application/json"):
        self.status_code = status
        self.payload = payload
        self.content = content if payload is None else json.dumps(payload).encode()
        self.headers = {"Content-Type": content_type, **(headers or {})}
        self.encoding = "utf-8"
        self.closed = False

    def json(self):
        if self.payload is None:
            raise ValueError("not json")
        return self.payload

    def iter_content(self, size):
        for start in range(0, len(self.content), size):
            yield self.content[start:start + size]

    def close(self):
        self.closed = True


def _work(**extra) -> dict:
    work = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1145/872757.872770",
        "title": "Winnowing: local algorithms for document fingerprinting",
        "publication_year": 2003,
        "authorships": [
            {"author": {"display_name": "Saul Schleimer"}},
            {"author": {"display_name": "Daniel S. Wilkerson"}},
            {"author": {"display_name": "Alex Aiken"}},
        ],
        "primary_location": {
            "landing_page_url": "https://dl.acm.org/doi/10.1145/872757.872770",
            "source": {"display_name": "SIGMOD"},
        },
        "best_oa_location": None,
        "open_access": {"is_oa": False, "oa_url": None},
        "locations": [],
        "abstract_inverted_index": _inverted(". ".join(ABSTRACT_SENTENCES) + "."),
    }
    work.update(extra)
    return work


def _openalex(*works, headers=None):
    return FakeResponse(payload={"meta": {"count": len(works)}, "results": list(works)}, headers=headers)


ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>arXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2101.00001v2</id>
    <title>Fingerprinting student
      programs at scale</title>
    <summary>  {summary}  </summary>
    <published>2021-01-04T10:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <arxiv:journal_ref>J. Plagiarism Stud. 3, 1 (2022)</arxiv:journal_ref>
    <link href="http://arxiv.org/pdf/2101.00001v2" rel="related" type="application/pdf" title="pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/cond-mat/0011267v1</id>
    <title>The electronic structure of cuprates</title>
    <summary>Spectroscopy of doped cuprate chains and ladders.</summary>
    <published>2000-11-15T16:19:15Z</published>
    <author><name>Mark S. Golden</name></author>
  </entry>
</feed>"""
ARXIV_ERROR = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format_for_x</id>
    <title>Error</title>
    <summary>bad query</summary>
  </entry>
</feed>"""


def _arxiv(summary: str = "Spectroscopy of nothing in particular.") -> FakeResponse:
    return FakeResponse(content=ARXIV_FEED.replace("{summary}", summary).encode(), content_type="application/atom+xml")


def _personal(text: str, name: str = "essay.txt"):
    return SubmissionFactory(
        user=UserFactory(), classroom=None, mime_type="text/plain", original_filename=name,
        file=ContentFile(text.encode("utf-8"), name=name),
    )


class TestQueries:
    def test_key_phrase_keeps_the_densest_eight_words_without_punctuation(self):
        sentence = (
            "In short, the guarantee holds because each window of consecutive hashes contributes its minimum (always)."
        )
        phrase = key_phrase(sentence)
        assert phrase == "the guarantee holds because each window of consecutive"
        assert phrase in sentence.replace(",", "")
        assert not any(c in phrase for c in ',()".')

    def test_boolean_words_in_a_sentence_are_not_operators(self):
        words = set(key_phrase("Cats AND dogs OR birds NOT fish swim together nicely today").split())
        assert not words & {"AND", "OR", "NOT"}
        assert {"and", "or", "not"} <= words

    def test_phrases_are_or_combined_under_the_url_budget(self):
        latin_terms = [(i, f'"{key_phrase(s)}"') for i, s in enumerate(PAPER_ESSAY.split(". "))]
        groups = or_groups(latin_terms, 2800)
        assert len(groups) == 1
        assert groups[0][0].count(" OR ") == 3 and groups[0][1] == [0, 1, 2, 3]
        cyrillic_terms = [(i, f'"{key_phrase(s)}"') for i, s in enumerate(RU_ESSAY.split(". ") * 4)]
        split = or_groups(cyrillic_terms, 2800)
        assert len(split) > 1
        assert sorted(i for _, members in split for i in members) == list(range(len(cyrillic_terms)))

    def test_abstract_is_rebuilt_from_the_inverted_index(self):
        assert rebuild_abstract({"local": [1], "Winnowing": [0], "algorithms": [2, 4], "and": [3]}) == (
            "Winnowing local algorithms and algorithms"
        )
        assert rebuild_abstract(None) == ""


class TestOpenAlex:
    @pytest.fixture(autouse=True)
    def _openalex_on(self, settings):
        settings.PLAGIARISM_OPENALEX = True
        settings.OPENALEX_API_KEY = ""
        settings.OPENALEX_MAILTO = "hello@prooflayer.cloud"

    @patch("plagiarism.academic.requests.get")
    def test_work_is_parsed_with_abstract_authors_venue_and_open_pdf(self, get):
        get.return_value = _openalex(_work(
            best_oa_location={"is_oa": True, "pdf_url": "https://example.org/winnowing.pdf", "landing_page_url": "https://example.org/w"},
            locations=[{"is_oa": False, "landing_page_url": "https://cyberleninka.ru/article/n/winnowing/pdf"}],
        ))
        papers = openalex_search('"each window of consecutive hashes contributes its minimum"')
        paper = papers[0]
        assert paper.engine == "openalex"
        assert paper.url == "https://doi.org/10.1145/872757.872770"
        assert paper.authors == ("Saul Schleimer", "Daniel S. Wilkerson", "Alex Aiken")
        assert paper.year == 2003 and paper.venue == "SIGMOD"
        assert paper.abstract.startswith("Winnowing selects a small subset")
        assert paper.fulltext == (
            "https://example.org/winnowing.pdf", "https://example.org/w", "https://cyberleninka.ru/article/n/winnowing/pdf",
        )
        params = get.call_args.kwargs["params"]
        assert params["mailto"] == "hello@prooflayer.cloud"
        assert "abstract_inverted_index" in params["select"]
        assert "Authorization" not in get.call_args.kwargs["headers"]

    @override_settings(OPENALEX_API_KEY="free-key")
    @patch("plagiarism.academic.requests.get")
    def test_optional_key_is_sent_and_dropped_when_refused(self, get):
        get.side_effect = [FakeResponse(status=403, payload={"error": "key_not_activated"}), _openalex(_work())]
        assert openalex_search('"winnowing selects a small subset of hashed substrings"')
        first, second = get.call_args_list
        assert first.kwargs["headers"]["Authorization"] == "Bearer free-key"
        assert "Authorization" not in second.kwargs["headers"]

    @patch("plagiarism.academic.requests.get")
    def test_answers_are_cached(self, get):
        get.return_value = _openalex(_work())
        query = '"winnowing selects a small subset of hashed substrings"'
        assert openalex_search(query) == openalex_search(query)
        assert get.call_count == 1

    @patch("plagiarism.academic.requests.get")
    def test_spent_budget_pauses_openalex(self, get):
        get.return_value = FakeResponse(status=429, payload={"error": "budget"}, headers={"Retry-After": "120"})
        assert openalex_search('"one phrase that will not be answered today at all"') is None
        assert openalex_search('"another phrase that will not be answered today"') is None
        assert get.call_count == 1

    @patch("plagiarism.academic.requests.get")
    def test_last_credits_pause_the_next_search(self, get):
        get.return_value = _openalex(_work(), headers={"X-RateLimit-Remaining": "5", "X-RateLimit-Reset": "600"})
        assert openalex_search('"the first search still answers with the last credits"')
        assert openalex_search('"the second search waits for tomorrow budget reset"') is None
        assert get.call_count == 1

    @patch("plagiarism.academic.requests.get", side_effect=ConnectionError("offline"))
    def test_lookup_that_never_answered_reports_no_phrases(self, _get):
        papers, answered = openalex_lookup([key_phrase(s) for s in PAPER_ESSAY.split(". ")])
        assert papers == [] and answered == set()

    @patch("plagiarism.academic.requests.get")
    def test_russian_phrases_are_searched_as_written(self, get):
        get.return_value = _openalex()
        phrases = [key_phrase(s) for s in RU_ESSAY.split(". ")]
        _, answered = openalex_lookup(phrases)
        assert answered == {0, 1, 2}
        query = get.call_args.kwargs["params"]["search"]
        assert '"' + phrases[0] + '"' in query and " OR " in query
        assert "language" not in get.call_args.kwargs["params"].get("filter", "")

    @override_settings(PLAGIARISM_OPENALEX=False)
    @patch("plagiarism.academic.requests.get")
    def test_switch_off_means_no_request(self, get):
        assert openalex_lookup(["winnowing selects a small subset of hashed substrings"]) == ([], set())
        get.assert_not_called()


@patch("plagiarism.academic.time")
class TestArxiv:
    @pytest.fixture(autouse=True)
    def _arxiv_on(self, settings):
        settings.PLAGIARISM_ARXIV = True

    def test_feed_is_parsed_into_papers(self, clock):
        papers = parse_arxiv(_arxiv("A summary.").content)
        first, second = papers
        assert first == Paper(
            engine="arxiv",
            url="https://arxiv.org/abs/2101.00001",
            title="Fingerprinting student programs at scale",
            authors=("Ada Lovelace", "Alan Turing"),
            year=2021,
            venue="J. Plagiarism Stud. 3, 1 (2022)",
            abstract="A summary.",
            fulltext=("https://arxiv.org/pdf/2101.00001",),
        )
        assert second.url == "https://arxiv.org/abs/cond-mat/0011267" and second.venue == "arXiv"

    def test_error_entry_is_not_an_answer(self, clock):
        assert parse_arxiv(ARXIV_ERROR.encode()) is None

    @patch("plagiarism.academic.requests.get")
    def test_requests_are_three_seconds_apart_and_cached(self, get, clock):
        clock.time.return_value = 300.0
        get.return_value = _arxiv()
        assert arxiv_search('all:"first phrase of the essay"') is not None
        assert arxiv_search('all:"second phrase of the essay"') is not None
        assert arxiv_search('all:"first phrase of the essay"') is not None
        assert get.call_count == 2
        assert [c.args[0] for c in clock.sleep.call_args_list] == [3.0]
        assert fetch_turn("https://arxiv.org/pdf/2101.00001")
        assert [c.args[0] for c in clock.sleep.call_args_list] == [3.0, 6.0]

    def test_no_free_turn_within_the_wait_limit_skips_arxiv(self, clock):
        clock.time.return_value = 300.0
        assert all(wait_turn("arxiv") for _ in range(11))
        assert not wait_turn("arxiv")

    @patch("plagiarism.academic.requests.get")
    def test_slow_down_answer_pauses_arxiv_and_its_pdfs(self, get, clock):
        clock.time.return_value = 300.0
        get.return_value = FakeResponse(status=429, content=b"Rate exceeded.", content_type="text/html")
        assert arxiv_search('all:"first phrase of the essay"') is None
        assert arxiv_search('all:"second phrase of the essay"') is None
        assert get.call_count == 1
        assert not fetch_turn("https://arxiv.org/pdf/2101.00001")
        assert fetch_turn("https://example.org/paper.pdf")

    @patch("plagiarism.academic.requests.get")
    def test_only_latin_script_phrases_go_to_arxiv(self, get, clock):
        clock.time.return_value = 300.0
        get.return_value = _arxiv()
        phrases = [key_phrase(s) for s in RU_ESSAY.split(". ")] + [key_phrase(PAPER_ESSAY.split(". ")[1])]
        papers, answered = arxiv_lookup(phrases)
        assert answered == {3}
        assert len(papers) == 2
        assert get.call_args.kwargs["params"]["search_query"] == f'all:"{phrases[3]}"'
        get.reset_mock()
        assert arxiv_lookup(phrases[:3]) == ([], set())
        get.assert_not_called()


class TestFetching:
    @patch("plagiarism.web.safe_get")
    def test_pdf_is_read_with_the_document_extractor(self, safe_get):
        safe_get.return_value = FakeResponse(content=_pdf(PAPER_ESSAY), content_type="application/pdf")
        text = fetch_text("https://example.org/paper.pdf")
        assert "consecutive hashes contributes its minimum" in " ".join(text.split())
        assert text == extract_pdf(_pdf(PAPER_ESSAY))
        assert safe_get.return_value.closed

    @patch("plagiarism.web.safe_get")
    def test_oversized_pdf_is_skipped(self, safe_get):
        huge = b"%PDF-1.4" + b"0" * (16 * 1024 * 1024)
        safe_get.return_value = FakeResponse(content=huge, content_type="application/pdf")
        assert fetch_text("https://example.org/huge.pdf") == ""

    @patch("plagiarism.web.safe_get")
    def test_binary_that_is_not_a_pdf_is_skipped(self, safe_get):
        safe_get.return_value = FakeResponse(content=b"PK\x03\x04 zip", content_type="application/octet-stream")
        assert fetch_text("https://example.org/file.bin") == ""

    @patch("plagiarism.web.fetch_text", return_value="Full text of the paper. " * 60)
    def test_full_text_is_cached(self, fetch):
        paper = Paper("openalex", "https://doi.org/10.1/x", "Title", fulltext=("https://example.org/x.pdf",))
        assert paper_text(paper) == paper_text(paper)
        fetch.assert_called_once()

    @patch("plagiarism.web.fetch_text", side_effect=["", "Landing page full text. " * 60])
    def test_next_full_text_link_is_tried_when_the_first_fails(self, fetch):
        paper = Paper("openalex", "https://doi.org/10.1/y", "Title", fulltext=("https://example.org/y.pdf", "https://example.org/y"))
        assert paper_text(paper).startswith("Landing page full text.")
        assert fetch.call_count == 2


def _routes(openalex=None, arxiv=None):
    def get(url, **kwargs):
        if "openalex" in url:
            if isinstance(openalex, Exception):
                raise openalex
            return openalex or _openalex()
        if isinstance(arxiv, Exception):
            raise arxiv
        return arxiv or _arxiv()
    return get


@pytest.mark.django_db
@patch("plagiarism.service.embed", side_effect=_fake_embed)
@patch("plagiarism.academic.time")
@patch("plagiarism.web.lookup", return_value=([], False))
class TestOriginalityWithPapers:
    @pytest.fixture(autouse=True)
    def _papers_on(self, settings):
        settings.PLAGIARISM_WEB_ENABLED = True
        settings.PLAGIARISM_OPENALEX = True
        settings.PLAGIARISM_ARXIV = True

    @patch("plagiarism.web.fetch_text", return_value="")
    @patch("plagiarism.academic.requests.get")
    def test_copied_abstract_is_a_paper_source_with_authors_year_and_venue(self, get, _fetch, _lookup, clock, _embed):
        clock.time.return_value = 300.0
        get.side_effect = _routes(openalex=_openalex(_work()))
        submission = _personal(PAPER_ESSAY)
        report = run_check(submission)
        assert report.web_status == PlagiarismReport.WebStatus.OK
        assert report.web_engines == ["arxiv", "openalex"]
        assert report.web_queries == 4
        paper = next(m for m in report.matches if m.get("engine") == "openalex")
        assert paper["source"] == "web" and paper["url"] == "https://doi.org/10.1145/872757.872770"
        assert report.originality < 60
        submission.refresh_from_db()
        row = next(r for r in report_payload(submission, submission.user)["matches"] if r["engine"] == "openalex")
        assert row["authors"] == ["Saul Schleimer", "Daniel S. Wilkerson", "Alex Aiken"]
        assert row["authors_total"] == 3
        assert row["year"] == 2003 and row["venue"] == "SIGMOD"
        assert row["source_excerpts"] and all(p.rstrip("…") in PAPER_ESSAY for p in row["source_excerpts"])

    @patch("plagiarism.web.safe_get")
    @patch("plagiarism.academic.requests.get")
    def test_open_access_pdf_finds_text_beyond_the_abstract(self, get, safe_get, _lookup, clock, _embed):
        clock.time.return_value = 300.0
        work = _work(
            abstract_inverted_index=_inverted("A short abstract about fingerprints."),
            best_oa_location={"is_oa": True, "pdf_url": "https://example.org/winnowing.pdf"},
        )
        get.side_effect = _routes(openalex=_openalex(work))
        pdf = _pdf("Introduction. " + PAPER_ESSAY + " Conclusion." * 80)
        safe_get.return_value = FakeResponse(content=pdf, content_type="application/pdf")
        report = run_check(_personal(PAPER_ESSAY))
        paper = next(m for m in report.matches if m.get("engine") == "openalex")
        assert paper["matched_chars"] > 300
        assert safe_get.call_args.args[0] == "https://example.org/winnowing.pdf"

    @patch("plagiarism.web.fetch_text")
    @patch("plagiarism.academic.requests.get")
    def test_arxiv_pdf_is_read_only_when_the_abstract_overlaps(self, get, fetch, _lookup, clock, _embed):
        clock.time.return_value = 300.0
        fetch.return_value = "Body. " + PAPER_ESSAY + " More body text." * 80
        get.side_effect = _routes(arxiv=_arxiv(ABSTRACT_SENTENCES[0] + "."))
        report = run_check(_personal(PAPER_ESSAY))
        fetched = [c.args[0] for c in fetch.call_args_list]
        assert fetched == ["https://arxiv.org/pdf/2101.00001"]
        arxiv = next(m for m in report.matches if m.get("engine") == "arxiv")
        assert arxiv["url"] == "https://arxiv.org/abs/2101.00001"
        assert arxiv["venue"] == "J. Plagiarism Stud. 3, 1 (2022)"

    @patch("plagiarism.web.fetch_text", return_value="")
    @patch("plagiarism.academic.requests.get")
    def test_reference_list_is_not_searched_or_matched(self, get, _fetch, _lookup, clock, _embed):
        clock.time.return_value = 300.0
        reference = BIBLIOGRAPHY.split("\n")[3]
        get.side_effect = _routes(openalex=_openalex(_work(abstract_inverted_index=_inverted(reference))))
        report = run_check(_personal(PAPER_ESSAY + BIBLIOGRAPHY))
        params = [c.kwargs["params"] for c in get.call_args_list]
        searched = " ".join(p.get("search", p.get("search_query", "")) for p in params)
        assert "Wilkerson" not in searched and "proceedings" not in searched
        assert not [m for m in report.matches if m.get("engine") == "openalex"]

    @patch("plagiarism.web.fetch_text", return_value="")
    @patch("plagiarism.academic.requests.get")
    def test_failed_paper_engines_are_not_named(self, get, _fetch, _lookup, clock, _embed):
        clock.time.return_value = 300.0
        get.side_effect = _routes(openalex=ConnectionError("offline"), arxiv=_arxiv())
        report = run_check(_personal(PAPER_ESSAY))
        assert report.web_status == PlagiarismReport.WebStatus.OK
        assert report.web_engines == ["arxiv"]

    @patch("plagiarism.web.fetch_text")
    @patch("plagiarism.academic.requests.get", side_effect=ConnectionError("offline"))
    def test_nothing_answered_is_a_failed_search(self, _get, fetch, _lookup, clock, _embed):
        clock.time.return_value = 300.0
        report = run_check(_personal(PAPER_ESSAY))
        assert report.web_status == PlagiarismReport.WebStatus.FAILED
        assert report.web_engines == [] and report.web_queries == 0
        fetch.assert_not_called()

    @patch("plagiarism.web.fetch_text", return_value="")
    @patch("plagiarism.academic.requests.get")
    def test_web_pages_that_never_opened_drop_the_web_engine(self, get, _fetch, lookup, clock, _embed):
        clock.time.return_value = 300.0
        lookup.return_value = ([Hit("https://example.org/essay", "Essay", "")], True)
        get.side_effect = _routes(openalex=_openalex(_work()))
        report = run_check(_personal(PAPER_ESSAY))
        assert report.web_status == PlagiarismReport.WebStatus.OK
        assert report.web_engines == ["arxiv", "openalex"]
