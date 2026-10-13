from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from analyzers.models import TrainingSample
from analyzers.training import snapshot
from billing.models import Subscription, get_or_create_subscription
from classroom.models import Classroom, Organization
from content.models import Submission
from content.retention import purge_expired_files
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory

PASSWORD = "Str0ng-pass-123"


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _user(**extra):
    user = UserFactory(is_verified=True, **extra)
    user.set_password(PASSWORD)
    user.save()
    return user


def _old(submission, days):
    Submission.objects.filter(pk=submission.pk).update(created_at=timezone.now() - timedelta(days=days))
    submission.refresh_from_db()
    return submission


@pytest.mark.django_db
class TestRetention:
    def test_personal_file_purged_after_90_days_verdict_kept(self):
        sub = _old(SubmissionFactory(final_verdict="fake", final_score=0.9), 91)
        assert purge_expired_files() == 1
        sub.refresh_from_db()
        assert not sub.file
        assert sub.final_verdict == "fake"
        assert "file_purged_at" in sub.metadata

    def test_recent_and_class_files_are_kept(self):
        recent = _old(SubmissionFactory(), 30)
        classroom = Classroom.create_for(UserFactory(), "8A")
        class_work = _old(SubmissionFactory(classroom=classroom), 400)
        assert purge_expired_files() == 0
        recent.refresh_from_db()
        class_work.refresh_from_db()
        assert recent.file and class_work.file

    def test_reanalyze_purged_file_is_refused(self):
        user = _user()
        sub = _old(SubmissionFactory(user=user, status="completed"), 91)
        purge_expired_files()
        response = _client(user).post(reverse("submission-reanalyze", kwargs={"id": sub.id}))
        assert response.status_code == 409


@pytest.mark.django_db
class TestAccountDeletion:
    def test_wrong_password_refused(self):
        user = _user()
        assert _client(user).delete(reverse("me"), {"password": "nope"}, format="json").status_code == 403

    def test_deletes_user_and_uploads(self):
        user = _user()
        SubmissionFactory(user=user)
        response = _client(user).delete(reverse("me"), {"password": PASSWORD}, format="json")
        assert response.status_code == 204
        assert not Submission.objects.filter(user_id=user.id).exists()

    def test_school_owner_must_delete_school_first(self):
        user = _user()
        Organization.create_for(user, "Lyceum", "lyceum-del")
        response = _client(user).delete(reverse("me"), {"password": PASSWORD}, format="json")
        assert response.status_code == 409
        assert response.data["code"] == "owns_organization"


@pytest.mark.django_db
class TestSchoolDeletion:
    def test_owner_deletes_school_with_all_class_work(self):
        owner = _user()
        sub = get_or_create_subscription(owner)
        sub.tier = Subscription.Tier.EDUCATION
        sub.save(update_fields=["tier"])
        org = Organization.create_for(owner, "Lyceum", "lyceum-gone")
        classroom = Classroom.create_for(owner, "8A", organization=org)
        work = SubmissionFactory(classroom=classroom)
        url = reverse("org-detail", kwargs={"slug": org.slug})
        assert _client(owner).delete(url, {"password": "wrong"}, format="json").status_code == 403
        assert _client(owner).delete(url, {"password": PASSWORD}, format="json").status_code == 204
        assert not Organization.objects.filter(pk=org.pk).exists()
        assert not Submission.objects.filter(pk=work.pk).exists()

    def test_teacher_cannot_delete_school(self):
        owner = _user()
        org = Organization.create_for(owner, "Lyceum", "lyceum-keep")
        stranger = _user()
        response = _client(stranger).delete(reverse("org-detail", kwargs={"slug": org.slug}), {"password": PASSWORD}, format="json")
        assert response.status_code == 403


@pytest.mark.django_db
class TestTrainingCorpus:
    def _labelled(self, user, **extra):
        return SubmissionFactory(user=user, status="completed", verified_label="fake", approved_for_training=True, **extra)

    def test_no_consent_no_sample(self):
        assert snapshot(self._labelled(_user())) is None
        assert not TrainingSample.objects.exists()

    def test_consented_sample_survives_account_deletion(self):
        user = _user(allow_training=True)
        sample = snapshot(self._labelled(user))
        assert sample is not None and sample.label == "fake"
        _client(user).delete(reverse("me"), {"password": PASSWORD}, format="json")
        assert TrainingSample.objects.filter(pk=sample.pk).exists()

    def test_withdrawing_consent_removes_samples(self):
        user = _user(allow_training=True)
        snapshot(self._labelled(user))
        response = _client(user).patch(reverse("me"), {"allow_training": False}, format="json")
        assert response.status_code == 200
        assert not TrainingSample.objects.exists()

    def test_deleting_account_can_also_remove_samples(self):
        user = _user(allow_training=True)
        snapshot(self._labelled(user))
        _client(user).delete(reverse("me"), {"password": PASSWORD, "forget_training": True}, format="json")
        assert not TrainingSample.objects.exists()

    def test_class_work_never_enters_the_corpus(self):
        user = _user(allow_training=True)
        classroom = Classroom.create_for(UserFactory(), "8A")
        assert snapshot(self._labelled(user, classroom=classroom)) is None

    def test_retention_does_not_touch_the_corpus(self):
        user = _user(allow_training=True)
        sub = self._labelled(user, file=ContentFile(b"\xff\xd8fakejpeg", name="a.jpg"))
        sample = snapshot(sub)
        _old(sub, 120)
        purge_expired_files()
        sample.refresh_from_db()
        assert sample.file
