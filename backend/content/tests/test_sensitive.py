import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from billing.models import Subscription, get_or_create_subscription
from classroom.models import Classroom, Membership
from content.admin import mark_sensitive, unmark_sensitive
from content.models import Submission
from content.sensitivity import parse_flag
from users.tests.factories import UserFactory

from .factories import SubmissionFactory

PHASH = 1234567


def _thumbnail(name):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 10, 10)).save(buf, format="JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _adult(**kwargs):
    return UserFactory(is_verified=True, is_adult=True, **kwargs)


def _minor(**kwargs):
    return UserFactory(is_verified=True, is_adult=False, **kwargs)


def _public(sensitive, **kwargs):
    return SubmissionFactory(
        status=Submission.Status.COMPLETED,
        is_public=True,
        is_sensitive=sensitive,
        final_verdict="fake",
        thumbnail=_thumbnail("sensitive_thumb.jpg" if sensitive else "safe_thumb.jpg"),
        **kwargs,
    )


def _feed_ids(response):
    results = response.data["results"] if isinstance(response.data, dict) else response.data
    return {item["id"]: item for item in results}


@pytest.mark.django_db
class TestPublicFeed:
    def setup_method(self):
        self.safe = _public(False)
        self.sensitive = _public(True)
        self.url = reverse("public-feed")

    def _assert_hidden(self, response):
        assert response.status_code == 200
        items = _feed_ids(response)
        assert str(self.safe.id) in items
        assert str(self.sensitive.id) not in items
        assert self.sensitive.thumbnail.name not in response.content.decode()
        assert items[str(self.safe.id)]["is_sensitive"] is False

    def test_anonymous_does_not_see_sensitive(self):
        self._assert_hidden(_client().get(self.url))

    def test_minor_does_not_see_sensitive(self):
        self._assert_hidden(_client(_minor()).get(self.url))

    def test_adult_sees_sensitive_flagged(self):
        response = _client(_adult()).get(self.url)
        assert response.status_code == 200
        items = _feed_ids(response)
        assert items[str(self.sensitive.id)]["is_sensitive"] is True
        assert items[str(self.sensitive.id)]["thumbnail_url"]

    def test_staff_sees_sensitive(self):
        response = _client(UserFactory(is_staff=True)).get(self.url)
        assert str(self.sensitive.id) in _feed_ids(response)

    def test_adult_with_real_token_sees_sensitive(self):
        adult = _adult()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(adult).access_token}")
        response = client.get(self.url)
        assert response.status_code == 200
        assert str(self.sensitive.id) in _feed_ids(response)

    def test_minor_with_real_token_does_not_see_sensitive(self):
        minor = _minor()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(minor).access_token}")
        self._assert_hidden(client.get(self.url))

    def test_broken_token_falls_back_to_anonymous(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
        self._assert_hidden(client.get(self.url))


@pytest.mark.django_db
class TestPublicDetail:
    def setup_method(self):
        self.sensitive = _public(True)
        self.url = reverse("public-submission-detail", kwargs={"id": self.sensitive.id})

    def test_anonymous_gets_404(self):
        response = _client().get(self.url)
        assert response.status_code == 404
        assert self.sensitive.thumbnail.name not in response.content.decode()

    def test_minor_gets_404(self):
        assert _client(_minor()).get(self.url).status_code == 404

    def test_adult_gets_flagged_item(self):
        response = _client(_adult()).get(self.url)
        assert response.status_code == 200
        assert response.data["is_sensitive"] is True
        assert response.data["thumbnail_url"]

    def test_safe_item_visible_to_anonymous(self):
        safe = _public(False)
        response = _client().get(reverse("public-submission-detail", kwargs={"id": safe.id}))
        assert response.status_code == 200
        assert response.data["is_sensitive"] is False


@pytest.mark.django_db
class TestStatusView:
    def setup_method(self):
        self.owner = _minor()
        self.sensitive = _public(True, user=self.owner)
        self.url = reverse("submission-status", kwargs={"id": self.sensitive.id})

    def test_anonymous_gets_404(self):
        assert _client().get(self.url).status_code == 404

    def test_other_minor_gets_404(self):
        assert _client(_minor()).get(self.url).status_code == 404

    def test_adult_sees_status(self):
        assert _client(_adult()).get(self.url).status_code == 200

    def test_owner_always_sees_own(self):
        assert _client(self.owner).get(self.url).status_code == 200


@pytest.mark.django_db
class TestSimilarSubmissions:
    def setup_method(self):
        self.sensitive = SubmissionFactory(
            status=Submission.Status.COMPLETED, phash=PHASH, is_sensitive=True, original_filename="nsfw.jpg",
        )
        self.safe = SubmissionFactory(status=Submission.Status.COMPLETED, phash=PHASH, original_filename="ok.jpg")

    def _similar(self, viewer):
        own = SubmissionFactory(user=viewer, status=Submission.Status.COMPLETED, phash=PHASH)
        response = _client(viewer).get(reverse("submission-detail", kwargs={"id": own.id}))
        assert response.status_code == 200
        return {item["id"]: item for item in response.data["similar_submissions"]}

    def test_minor_does_not_see_sensitive_match(self):
        similar = self._similar(_minor())
        assert str(self.safe.id) in similar
        assert str(self.sensitive.id) not in similar
        assert similar[str(self.safe.id)]["is_sensitive"] is False

    def test_adult_sees_sensitive_match_flagged(self):
        similar = self._similar(_adult())
        assert similar[str(self.sensitive.id)]["is_sensitive"] is True

    def test_compare_hides_sensitive_match_from_minor(self):
        minor = _minor()
        sub = get_or_create_subscription(minor)
        sub.tier = Subscription.Tier.PRO
        sub.save(update_fields=["tier"])
        first = SubmissionFactory(user=minor, status=Submission.Status.COMPLETED, phash=PHASH)
        second = SubmissionFactory(user=minor, status=Submission.Status.COMPLETED, phash=PHASH)
        response = _client(minor).get(reverse("submission-compare"), {"ids": f"{first.id},{second.id}"})
        assert response.status_code == 200
        for item in response.data:
            ids = {match["id"] for match in item["similar_submissions"]}
            assert str(self.sensitive.id) not in ids
            assert str(self.safe.id) in ids


@pytest.mark.django_db
class TestSupervisedAccess:
    def _class_with_student(self, teacher):
        sub = get_or_create_subscription(teacher)
        sub.tier = Subscription.Tier.EDUCATION
        sub.save(update_fields=["tier"])
        classroom = Classroom.create_for(teacher, "Media literacy")
        student = _minor()
        Membership.objects.create(classroom=classroom, user=student)
        work = SubmissionFactory(
            user=student, classroom=classroom, status=Submission.Status.COMPLETED, is_sensitive=True,
        )
        return student, work

    def test_minor_supervisor_cannot_open_sensitive_work(self):
        teacher = _minor()
        _, work = self._class_with_student(teacher)
        response = _client(teacher).get(reverse("submission-detail", kwargs={"id": work.id}))
        assert response.status_code == 404

    def test_adult_supervisor_opens_sensitive_work(self):
        teacher = _adult()
        _, work = self._class_with_student(teacher)
        response = _client(teacher).get(reverse("submission-detail", kwargs={"id": work.id}))
        assert response.status_code == 200
        assert response.data["is_sensitive"] is True

    def test_minor_author_opens_own_sensitive_work(self):
        student, work = self._class_with_student(_adult())
        response = _client(student).get(reverse("submission-detail", kwargs={"id": work.id}))
        assert response.status_code == 200
        assert response.data["file_url"]


@pytest.mark.django_db
class TestTogglePublic:
    def _url(self, submission):
        return reverse("submission-toggle-public", kwargs={"id": submission.id})

    def test_minor_cannot_publish(self):
        minor = _minor()
        submission = SubmissionFactory(user=minor, status=Submission.Status.COMPLETED)
        response = _client(minor).post(self._url(submission), {}, format="json")
        assert response.status_code == 403
        assert response.data == {
            "detail": "Publishing to the public feed is available from age 18.",
            "code": "adult_required",
        }
        submission.refresh_from_db()
        assert submission.is_public is False

    def test_minor_can_unpublish(self):
        minor = _minor()
        submission = SubmissionFactory(user=minor, status=Submission.Status.COMPLETED, is_public=True)
        response = _client(minor).post(self._url(submission), {}, format="json")
        assert response.status_code == 200
        assert response.data["is_public"] is False
        submission.refresh_from_db()
        assert submission.is_public is False

    def test_adult_can_publish(self):
        adult = _adult()
        submission = SubmissionFactory(user=adult, status=Submission.Status.COMPLETED)
        response = _client(adult).post(self._url(submission), {}, format="json")
        assert response.status_code == 200
        assert response.data == {"is_public": True, "is_sensitive": False}

    def test_adult_can_publish_as_sensitive(self):
        adult = _adult()
        submission = SubmissionFactory(user=adult, status=Submission.Status.COMPLETED)
        response = _client(adult).post(self._url(submission), {"sensitive": True}, format="json")
        assert response.status_code == 200
        assert response.data == {"is_public": True, "is_sensitive": True}
        submission.refresh_from_db()
        assert submission.is_public is True
        assert submission.is_sensitive is True

    def test_publishing_without_flag_keeps_staff_mark(self):
        adult = _adult()
        submission = SubmissionFactory(user=adult, status=Submission.Status.COMPLETED, is_sensitive=True)
        response = _client(adult).post(self._url(submission), {"sensitive": False}, format="json")
        assert response.status_code == 200
        submission.refresh_from_db()
        assert submission.is_sensitive is True

    def test_staff_can_publish(self):
        staff = UserFactory(is_verified=True, is_staff=True)
        submission = SubmissionFactory(user=staff, status=Submission.Status.COMPLETED)
        response = _client(staff).post(self._url(submission), {}, format="json")
        assert response.status_code == 200
        assert response.data["is_public"] is True

    def test_class_work_still_blocked_for_adult(self):
        adult = _adult()
        get_or_create_subscription(adult)
        classroom = Classroom.create_for(adult, "Class")
        submission = SubmissionFactory(user=adult, classroom=classroom, status=Submission.Status.COMPLETED)
        response = _client(adult).post(self._url(submission), {}, format="json")
        assert response.status_code == 403
        assert "class" in response.data["detail"]


@pytest.mark.django_db
class TestStaffSensitiveControls:
    def setup_method(self):
        self.staff = UserFactory(is_staff=True)
        self.sub = SubmissionFactory(status=Submission.Status.COMPLETED, final_verdict="needs_review")
        self.url = reverse("review-override", kwargs={"id": self.sub.id})

    def test_override_can_mark_sensitive(self):
        response = _client(self.staff).post(
            self.url, {"verdict": "fake", "reason": "r", "is_sensitive": True}, format="json",
        )
        assert response.status_code == 201
        self.sub.refresh_from_db()
        assert self.sub.is_sensitive is True

    def test_override_can_unmark_sensitive(self):
        self.sub.is_sensitive = True
        self.sub.save(update_fields=["is_sensitive"])
        response = _client(self.staff).post(
            self.url, {"verdict": "fake", "reason": "r", "is_sensitive": False}, format="json",
        )
        assert response.status_code == 201
        self.sub.refresh_from_db()
        assert self.sub.is_sensitive is False

    def test_override_without_field_keeps_flag(self):
        self.sub.is_sensitive = True
        self.sub.save(update_fields=["is_sensitive"])
        response = _client(self.staff).post(self.url, {"verdict": "fake", "reason": "r"}, format="json")
        assert response.status_code == 201
        self.sub.refresh_from_db()
        assert self.sub.is_sensitive is True

    def test_override_rejects_garbage_flag(self):
        response = _client(self.staff).post(
            self.url, {"verdict": "fake", "reason": "r", "is_sensitive": "maybe"}, format="json",
        )
        assert response.status_code == 400
        self.sub.refresh_from_db()
        assert self.sub.final_verdict == "needs_review"

    def test_review_queue_exposes_flag(self):
        self.sub.is_sensitive = True
        self.sub.save(update_fields=["is_sensitive"])
        response = _client(self.staff).get(reverse("review-queue"))
        results = response.data["results"] if isinstance(response.data, dict) else response.data
        assert results[0]["is_sensitive"] is True

    def test_admin_actions(self):
        other = SubmissionFactory()
        mark_sensitive(None, None, Submission.objects.filter(id__in=[self.sub.id, other.id]))
        assert Submission.objects.filter(is_sensitive=True).count() == 2
        unmark_sensitive(None, None, Submission.objects.filter(id=other.id))
        assert list(Submission.objects.filter(is_sensitive=True)) == [self.sub]


class TestParseFlag:
    @pytest.mark.parametrize("value,expected", [
        (True, True), ("true", True), ("1", True), (False, False), ("false", False), ("0", False),
        (None, None), ("maybe", None), ([1], None),
    ])
    def test_parse(self, value, expected):
        assert parse_flag(value) is expected
