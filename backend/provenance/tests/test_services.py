import pytest
from unittest.mock import patch, MagicMock

from content.tests.factories import SubmissionFactory
from provenance.models import ProvenanceResult
from provenance.services import (
    check_perceptual_known_fake,
    find_clip_neighbors,
    scan_provenance,
)


@pytest.mark.django_db
class TestCheckPerceptualKnownFake:
    def test_no_phash_returns_false(self):
        submission = SubmissionFactory()
        submission.phash = None
        assert check_perceptual_known_fake(submission) is False


@pytest.mark.django_db
class TestFindClipNeighbors:
    def test_no_embedding_returns_empty(self):
        submission = SubmissionFactory()
        submission.clip_embedding = None
        result = find_clip_neighbors(submission)
        assert result == []


@pytest.mark.django_db
class TestScanProvenance:
    def test_all_internal_failures_handled_gracefully(self):
        submission = SubmissionFactory()
        with (
            patch("provenance.services.run_phash_lookup", side_effect=Exception("phash error")),
            patch("provenance.services.run_clip_neighbor_lookup", side_effect=Exception("clip error")),
            patch("provenance.services.extract_c2pa", side_effect=Exception("c2pa error")),
        ):
            result = scan_provenance(submission)
        assert result == []

    def test_c2pa_skipped_when_not_installed(self):
        submission = SubmissionFactory()
        with (
            patch("provenance.services.run_phash_lookup", return_value=[]),
            patch("provenance.services.run_clip_neighbor_lookup", return_value=[]),
            patch("provenance.services.extract_c2pa", return_value=None),
        ):
            result = scan_provenance(submission)
        assert result == []

    def test_returns_combined_results(self):
        submission = SubmissionFactory()
        fake_result = MagicMock(spec=ProvenanceResult)
        with (
            patch("provenance.services.run_phash_lookup", return_value=[fake_result]),
            patch("provenance.services.run_clip_neighbor_lookup", return_value=[]),
            patch("provenance.services.extract_c2pa", return_value=None),
        ):
            result = scan_provenance(submission)
        assert fake_result in result


@pytest.mark.django_db
class TestRunPhashLookup:
    def test_no_similar_returns_empty(self):
        from provenance.services import run_phash_lookup
        submission = SubmissionFactory()
        with patch("content.services.find_similar_submissions", return_value=[]):
            result = run_phash_lookup(submission)
        assert result == []

    def test_creates_provenance_result_for_match(self):
        from provenance.services import run_phash_lookup
        submission = SubmissionFactory()
        similar = [{"id": str(submission.id), "filename": "match.jpg", "distance": 5}]
        with patch("content.services.find_similar_submissions", return_value=similar):
            results = run_phash_lookup(submission)
        assert len(results) == 1
        assert results[0].source_type == ProvenanceResult.SourceType.PHASH_MATCH
        assert results[0].similarity_score == pytest.approx(1.0 - 5 / 64.0, abs=0.001)


@pytest.mark.django_db
class TestExtractC2pa:
    def test_returns_none_when_c2pa_not_installed(self):
        from provenance.services import extract_c2pa
        submission = SubmissionFactory()
        with patch.dict("sys.modules", {"c2pa": None}):
            result = extract_c2pa(submission)
        assert result is None
