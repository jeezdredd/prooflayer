import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from content.pdf import build_report_context
from content.tests.factories import SubmissionFactory
from provenance.models import ProvenanceResult
from users.tests.factories import UserFactory


def _matches(own):
    sensitive = SubmissionFactory(user=own.user, is_sensitive=True, original_filename="nsfw.jpg")
    safe = SubmissionFactory(user=own.user, original_filename="ok.jpg")
    for match in (sensitive, safe):
        ProvenanceResult.objects.create(
            submission=own,
            source_type=ProvenanceResult.SourceType.PHASH_MATCH,
            similarity_score=0.9,
            raw_data={"submission_id": str(match.id), "distance": 3},
        )
    return sensitive, safe


@pytest.mark.django_db
class TestProvenanceSensitiveMatches:
    def _results(self, viewer):
        own = SubmissionFactory(user=viewer)
        sensitive, _safe = _matches(own)
        ProvenanceResult.objects.create(
            submission=own,
            source_type=ProvenanceResult.SourceType.TINEYE,
            source_url="https://example.com/a.jpg",
            raw_data={"submission_id": "not-a-uuid"},
        )
        client = APIClient()
        client.force_authenticate(user=viewer)
        response = client.get(reverse("provenance-list", kwargs={"submission_id": own.id}))
        assert response.status_code == 200
        return response, sensitive

    def test_minor_does_not_see_sensitive_match(self):
        response, sensitive = self._results(UserFactory(is_adult=False))
        titles = {item["title"] for item in response.data}
        assert "nsfw.jpg" not in titles
        assert "ok.jpg" in titles
        assert len(response.data) == 2
        assert str(sensitive.id) not in response.content.decode()

    def test_adult_sees_sensitive_match_flagged(self):
        response, _sensitive = self._results(UserFactory(is_adult=True))
        flags = {item["title"]: item["is_sensitive"] for item in response.data if item["match"]}
        assert flags == {"nsfw.jpg": True, "ok.jpg": False}
        assert len(response.data) == 3


@pytest.mark.django_db
class TestPdfSensitiveMatches:
    def _lines(self, viewer):
        own = SubmissionFactory(user=viewer)
        _matches(own)
        return " ".join(p["title"] for p in build_report_context(own, viewer)["provenance"])

    def test_minor_pdf_omits_sensitive_match(self):
        lines = self._lines(UserFactory(is_adult=False))
        assert "ok.jpg" in lines and "nsfw.jpg" not in lines

    def test_adult_pdf_keeps_sensitive_match(self):
        lines = self._lines(UserFactory(is_adult=True))
        assert "ok.jpg" in lines and "nsfw.jpg" in lines

    def test_pdf_hides_a_strangers_file_name(self):
        viewer = UserFactory(is_adult=True)
        own = SubmissionFactory(user=viewer)
        stranger = SubmissionFactory(original_filename="private-photo.jpg")
        ProvenanceResult.objects.create(
            submission=own,
            source_type=ProvenanceResult.SourceType.PHASH_MATCH,
            title="private-photo.jpg",
            similarity_score=0.97,
            raw_data={"submission_id": str(stranger.id), "distance": 1},
        )
        lines = [p["title"] for p in build_report_context(own, viewer)["provenance"]]
        assert lines == ["The same picture was already checked on ProofLayer"]
