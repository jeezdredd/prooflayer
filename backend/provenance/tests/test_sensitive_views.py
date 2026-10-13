from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.test import APIClient

from content.pdf import generate_report_pdf
from content.tests.factories import SubmissionFactory
from provenance.models import ProvenanceResult
from users.tests.factories import UserFactory


@pytest.mark.django_db
class TestProvenanceSensitiveMatches:
    def setup_method(self):
        self.sensitive = SubmissionFactory(is_sensitive=True, original_filename="nsfw.jpg")
        self.safe = SubmissionFactory(original_filename="ok.jpg")

    def _results(self, viewer):
        own = SubmissionFactory(user=viewer)
        for match in (self.sensitive, self.safe):
            ProvenanceResult.objects.create(
                submission=own,
                source_type=ProvenanceResult.SourceType.PHASH_MATCH,
                title=match.original_filename,
                similarity_score=0.9,
                raw_data={"submission_id": str(match.id), "distance": 3},
            )
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
        return response

    def test_minor_does_not_see_sensitive_match(self):
        response = self._results(UserFactory(is_adult=False))
        titles = {item["title"] for item in response.data}
        assert "nsfw.jpg" not in titles
        assert "ok.jpg" in titles
        assert len(response.data) == 2
        assert str(self.sensitive.id) not in response.content.decode()

    def test_adult_sees_sensitive_match_flagged(self):
        response = self._results(UserFactory(is_adult=True))
        flags = {item["title"]: item["is_sensitive"] for item in response.data}
        assert flags["nsfw.jpg"] is True
        assert flags["ok.jpg"] is False
        assert len(response.data) == 3


class StopRender(Exception):
    pass


@pytest.mark.django_db
class TestPdfSensitiveMatches:
    def _titles(self, viewer):
        own = SubmissionFactory(user=viewer)
        for match in (SubmissionFactory(is_sensitive=True, original_filename="nsfw.jpg"), SubmissionFactory(original_filename="ok.jpg")):
            ProvenanceResult.objects.create(
                submission=own,
                source_type=ProvenanceResult.SourceType.PHASH_MATCH,
                title=match.original_filename,
                similarity_score=0.9,
                raw_data={"submission_id": str(match.id), "distance": 3},
            )
        request = RequestFactory().get("/")
        request.user = viewer
        with patch("content.pdf.render_to_string", side_effect=StopRender) as render:
            with pytest.raises(StopRender):
                generate_report_pdf(own, request)
        return {p.title for p in render.call_args.args[1]["provenance_results"]}

    def test_minor_pdf_omits_sensitive_match(self):
        assert self._titles(UserFactory(is_adult=False)) == {"ok.jpg"}

    def test_adult_pdf_keeps_sensitive_match(self):
        assert self._titles(UserFactory(is_adult=True)) == {"ok.jpg", "nsfw.jpg"}
