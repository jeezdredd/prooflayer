import io
from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Subscription, get_or_create_subscription
from classroom.models import Classroom, Membership, Organization, OrgMember
from content.models import Submission, VerdictObjection
from content.services import find_similar_submissions
from content.tasks import process_submission
from content.tests.factories import SubmissionFactory
from users import mail as user_mail
from users.tasks import send_objection_notice
from users.tests.factories import UserFactory

PHASH = 987654321


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _detail(user, submission):
    return _client(user).get(reverse("submission-detail", kwargs={"id": submission.id}))


def _plan(user, tier):
    sub = get_or_create_subscription(user)
    sub.tier = tier
    sub.save(update_fields=["tier"])


def _school(owner_tier=Subscription.Tier.EDUCATION):
    owner = UserFactory(is_verified=True)
    _plan(owner, owner_tier)
    org = Organization.create_for(owner, "Lyceum 239", "lyceum-239")
    teacher = UserFactory(is_verified=True, first_name="Игорь", last_name="Орлов")
    OrgMember.objects.create(organization=org, user=teacher, role=OrgMember.Role.TEACHER)
    classroom = Classroom.create_for(teacher, "9Б", organization=org)
    student = UserFactory(is_verified=True, first_name="Ольга", last_name="Смирнова")
    Membership.objects.create(classroom=classroom, user=student)
    work = SubmissionFactory(user=student, classroom=classroom, status=Submission.Status.COMPLETED, final_verdict="suspicious")
    return owner, teacher, classroom, student, work


@pytest.mark.django_db
class TestViewerRole:
    def test_supervising_teacher(self):
        _owner, teacher, classroom, _student, work = _school()
        data = _detail(teacher, work).data
        assert data["viewer_role"] == "supervisor"
        assert data["student_name"] == "Ольга Смирнова"
        assert data["classroom_name"] == "9Б"
        assert data["classroom"] == {"id": str(classroom.id), "name": "9Б", "organization_slug": "lyceum-239"}
        assert data["can_object"] is False
        assert data["can_publish"] is False

    def test_school_admin_supervises_too(self):
        owner, _teacher, _classroom, _student, work = _school()
        assert _detail(owner, work).data["viewer_role"] == "supervisor"

    def test_student_author(self):
        _owner, _teacher, _classroom, student, work = _school()
        data = _detail(student, work).data
        assert data["viewer_role"] == "author"
        assert data["student_name"] == "Ольга Смирнова"
        assert data["classroom_name"] == "9Б"
        assert data["can_object"] is True
        assert data["can_publish"] is False

    def test_teacher_own_upload_into_own_class_cannot_object(self):
        _owner, teacher, classroom, _student, _work = _school()
        own = SubmissionFactory(user=teacher, classroom=classroom, status=Submission.Status.COMPLETED)
        data = _detail(teacher, own).data
        assert data["viewer_role"] == "author"
        assert data["can_object"] is False

    def test_personal_check_can_be_published(self):
        author = UserFactory(is_verified=True, is_adult=True)
        work = SubmissionFactory(user=author, status=Submission.Status.COMPLETED)
        data = _detail(author, work).data
        assert data["viewer_role"] == "author"
        assert data["classroom"] is None and data["classroom_name"] is None
        assert data["can_publish"] is True and data["can_object"] is True


@pytest.mark.django_db
class TestReportPdfAccess:
    def _pdf(self, user, work):
        with patch("content.views.generate_report_pdf", return_value=io.BytesIO(b"%PDF-1.4")):
            return _client(user).get(reverse("submission-report-pdf", kwargs={"id": work.id}))

    def test_invited_teacher_on_free_plan_downloads_class_report(self):
        _owner, teacher, _classroom, _student, work = _school()
        assert get_or_create_subscription(teacher).tier == Subscription.Tier.FREE
        response = self._pdf(teacher, work)
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_student_downloads_own_class_report_under_school_plan(self):
        _owner, _teacher, _classroom, student, work = _school()
        assert self._pdf(student, work).status_code == 200

    def test_school_without_pdf_gets_plain_school_message(self):
        _owner, _teacher, _classroom, student, work = _school(owner_tier=Subscription.Tier.FREE)
        response = self._pdf(student, work)
        assert response.status_code == 402
        assert response.data["code"] == "school_plan_required"

    def test_personal_work_still_needs_pro(self):
        author = UserFactory(is_verified=True)
        work = SubmissionFactory(user=author, status=Submission.Status.COMPLETED)
        response = self._pdf(author, work)
        assert response.status_code == 402
        assert response.data["code"] == "upgrade_required"

    def test_stranger_gets_404(self):
        _owner, _teacher, _classroom, _student, work = _school()
        assert self._pdf(UserFactory(is_verified=True), work).status_code == 404


@pytest.mark.django_db
class TestObjectionLink:
    def test_class_objection_email_links_to_classroom(self, settings):
        settings.CLASSROOM_URL = "https://classroom.example"
        _owner, _teacher, _classroom, student, work = _school()
        objection = VerdictObjection.objects.create(submission=work, author=student, reason="I wrote it myself, here is my draft.")
        with patch("users.tasks.mail.objection_context", wraps=user_mail.objection_context) as context:
            send_objection_notice(str(objection.id))
        assert context.call_args.kwargs["link"] == f"https://classroom.example/results/{work.id}"


@pytest.mark.django_db
class TestSimilarityScope:
    def test_class_work_is_compared_within_the_school_only(self):
        _owner, _teacher, classroom, student, work = _school()
        work.phash = PHASH
        work.save(update_fields=["phash"])
        org = classroom.organization
        colleague = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=org, user=colleague, role=OrgMember.Role.TEACHER)
        same_school = SubmissionFactory(classroom=Classroom.create_for(colleague, "10А", organization=org), phash=PHASH)
        other_owner = UserFactory(is_verified=True)
        other_org = Organization.create_for(other_owner, "School 5", "school-5")
        other_school = SubmissionFactory(classroom=Classroom.create_for(other_owner, "7В", organization=other_org), phash=PHASH)
        own_earlier = SubmissionFactory(user=student, phash=PHASH)
        ids = {m["id"] for m in find_similar_submissions(work)}
        assert ids == {str(same_school.id), str(own_earlier.id)}
        assert str(other_school.id) not in ids


@pytest.mark.django_db
class TestCachedUploadProvenance:
    def test_cache_hit_still_looks_for_the_same_picture(self):
        _owner, _teacher, classroom, student, first = _school()
        second = SubmissionFactory(user=student, classroom=classroom)
        with (
            patch("content.tasks.find_cached_result", return_value=first),
            patch("content.tasks.scan_provenance") as scan,
        ):
            process_submission(str(second.id))
        second.refresh_from_db()
        assert second.status == Submission.Status.COMPLETED
        scan.assert_called_once()
        assert scan.call_args.args[0].id == second.id
