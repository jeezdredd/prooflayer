import pytest

from content.models import Submission, KnownFakeHash
from .factories import SubmissionFactory


@pytest.mark.django_db
class TestSubmission:
    def test_create_submission(self):
        sub = SubmissionFactory()
        assert sub.id is not None
        assert sub.status == Submission.Status.PENDING
        assert sub.original_filename.startswith("test_image_")

    def test_uuid_primary_key(self):
        sub = SubmissionFactory()
        assert len(str(sub.id)) == 36

    def test_default_status(self):
        sub = SubmissionFactory()
        assert sub.status == "pending"


@pytest.mark.django_db
class TestKnownFakeHash:
    def test_create(self):
        kfh = KnownFakeHash.objects.create(
            sha256_hash="a" * 64,
            source="test",
            description="test fake",
        )
        assert kfh.sha256_hash == "a" * 64
