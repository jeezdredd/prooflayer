from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from classroom.models import Classroom, Membership, Organization, OrgMember
from content.models import VerdictObjection, add_business_days
from content.objections import latest_objection_payload
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory

REASON = "I drew this myself, here are my sketches."
ANSWER = "Reviewed the sketches, the work is yours."


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _at(year, month, day, hour=10):
    return datetime(year, month, day, hour, 30, tzinfo=dt_timezone.utc)


def _school_class():
    owner = UserFactory(is_verified=True)
    org = Organization.create_for(owner, "Lyceum 239", "lyceum-239")
    teacher = UserFactory(is_verified=True)
    OrgMember.objects.create(organization=org, user=teacher, role=OrgMember.Role.TEACHER)
    classroom = Classroom.create_for(teacher, "8A", organization=org)
    student = UserFactory(is_verified=True)
    Membership.objects.create(classroom=classroom, user=student)
    return owner, teacher, classroom, student


def _work(student, classroom=None, **extra):
    extra.setdefault("status", "completed")
    return SubmissionFactory(user=student, classroom=classroom, final_verdict="fake", final_score=0.9, **extra)


def _object(user, submission, reason=REASON):
    return _client(user).post(
        reverse("submission-objection", kwargs={"id": submission.id}), {"reason": reason}, format="json",
    )


def _respond(user, objection_id, decision="upheld", response=ANSWER):
    return _client(user).post(
        reverse("objection-respond", kwargs={"id": objection_id}),
        {"decision": decision, "response": response},
        format="json",
    )


class TestAddBusinessDays:
    def test_midweek_stays_in_week(self):
        assert add_business_days(_at(2026, 10, 12), 3) == _at(2026, 10, 15)

    def test_thursday_skips_weekend(self):
        assert add_business_days(_at(2026, 10, 15), 3) == _at(2026, 10, 20)

    def test_friday_lands_on_wednesday(self):
        assert add_business_days(_at(2026, 10, 16), 3) == _at(2026, 10, 21)

    def test_saturday_and_sunday_start_count_from_monday(self):
        assert add_business_days(_at(2026, 10, 17), 3) == _at(2026, 10, 21)
        assert add_business_days(_at(2026, 10, 18), 3) == _at(2026, 10, 21)

    def test_keeps_time_of_day(self):
        assert add_business_days(_at(2026, 10, 16, 23), 1) == _at(2026, 10, 19, 23)

    def test_zero_days_is_identity(self):
        assert add_business_days(_at(2026, 10, 17), 0) == _at(2026, 10, 17)


@pytest.mark.django_db
class TestFiling:
    def test_author_files_and_teacher_is_emailed(self, django_capture_on_commit_callbacks):
        _owner, teacher, classroom, student = _school_class()
        work = _work(student, classroom)
        with django_capture_on_commit_callbacks(execute=True):
            response = _object(student, work)
        assert response.status_code == 201
        assert response.data["status"] == "open"
        assert response.data["student"] == student.username
        assert response.data["classroom"] == "8A"
        assert response.data["overdue"] is False
        objection = VerdictObjection.objects.get(id=response.data["id"])
        assert objection.due_at > objection.created_at + timedelta(days=2)
        assert [m.to for m in mail.outbox] == [[teacher.email]]

    def test_due_at_is_three_business_days_after_filing(self):
        _owner, _teacher, classroom, student = _school_class()
        friday = _at(2026, 10, 16)
        with patch("django.utils.timezone.now", return_value=friday):
            response = _object(student, _work(student, classroom))
        assert response.status_code == 201
        objection = VerdictObjection.objects.get(id=response.data["id"])
        assert objection.due_at == _at(2026, 10, 21)

    def test_personal_work_emails_admins_or_skips(self, settings, django_capture_on_commit_callbacks):
        author = UserFactory(is_verified=True)
        settings.ADMINS = [("Ops", "ops@prooflayer.test")]
        with django_capture_on_commit_callbacks(execute=True):
            assert _object(author, _work(author)).status_code == 201
        assert [m.to for m in mail.outbox] == [["ops@prooflayer.test"]]
        settings.ADMINS = []
        other = UserFactory(is_verified=True)
        with django_capture_on_commit_callbacks(execute=True):
            assert _object(other, _work(other)).status_code == 201
        assert len(mail.outbox) == 1

    def test_email_failure_does_not_break_request(self, django_capture_on_commit_callbacks):
        _owner, _teacher, classroom, student = _school_class()
        with patch("users.mail.deliver", side_effect=RuntimeError("smtp down")):
            with django_capture_on_commit_callbacks(execute=True):
                response = _object(student, _work(student, classroom))
        assert response.status_code == 201

    def test_only_author_can_file(self):
        _owner, teacher, classroom, student = _school_class()
        work = _work(student, classroom)
        assert _object(teacher, work).status_code == 403
        assert _object(UserFactory(is_verified=True), work).status_code == 404
        assert not VerdictObjection.objects.exists()

    def test_unfinished_work_refused(self):
        author = UserFactory(is_verified=True)
        assert _object(author, _work(author, status="processing")).status_code == 400

    @pytest.mark.parametrize("reason", ["", "too short", "x" * 2001])
    def test_reason_length_validated(self, reason):
        author = UserFactory(is_verified=True)
        assert _object(author, _work(author), reason=reason).status_code == 400

    def test_one_open_objection_at_a_time(self):
        _owner, teacher, classroom, student = _school_class()
        work = _work(student, classroom)
        first = _object(student, work)
        assert first.status_code == 201
        assert _object(student, work).status_code == 409
        assert _respond(teacher, first.data["id"]).status_code == 200
        assert _object(student, work).status_code == 201
        assert work.objections.count() == 2


@pytest.mark.django_db
class TestVisibilityAndAnswer:
    def test_supervisor_sees_and_answers(self):
        owner, teacher, classroom, student = _school_class()
        objection_id = _object(student, _work(student, classroom)).data["id"]
        for viewer in (teacher, owner, student):
            response = _client(viewer).get(reverse("objection-list"))
            assert [row["id"] for row in response.data["results"]] == [objection_id]
        response = _respond(teacher, objection_id, decision="changed")
        assert response.status_code == 200
        assert response.data["status"] == "answered"
        assert response.data["decision"] == "changed"
        assert response.data["response"] == ANSWER
        objection = VerdictObjection.objects.get(id=objection_id)
        assert objection.responded_by == teacher
        assert objection.responded_at is not None
        assert _respond(owner, objection_id).status_code == 409

    def test_status_filter(self):
        _owner, teacher, classroom, student = _school_class()
        answered = _object(student, _work(student, classroom)).data["id"]
        _respond(teacher, answered)
        still_open = _object(student, _work(student, classroom)).data["id"]
        url = reverse("objection-list")
        assert [r["id"] for r in _client(teacher).get(url, {"status": "open"}).data["results"]] == [still_open]
        assert [r["id"] for r in _client(teacher).get(url, {"status": "answered"}).data["results"]] == [answered]

    def test_other_teacher_of_same_school_cannot_see_or_answer(self):
        _owner, _teacher, classroom, student = _school_class()
        objection_id = _object(student, _work(student, classroom)).data["id"]
        colleague = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=classroom.organization, user=colleague, role=OrgMember.Role.TEACHER)
        assert _client(colleague).get(reverse("objection-list")).data["results"] == []
        assert _respond(colleague, objection_id).status_code == 403

    def test_student_cannot_answer(self):
        _owner, _teacher, classroom, student = _school_class()
        objection_id = _object(student, _work(student, classroom)).data["id"]
        classmate = UserFactory(is_verified=True)
        Membership.objects.create(classroom=classroom, user=classmate)
        assert _respond(student, objection_id).status_code == 403
        assert _respond(classmate, objection_id).status_code == 403
        assert _client(classmate).get(reverse("objection-list")).data["results"] == []
        assert VerdictObjection.objects.get(id=objection_id).status == "open"

    def test_staff_answers_personal_work(self):
        author = UserFactory(is_verified=True)
        objection_id = _object(author, _work(author)).data["id"]
        staff = UserFactory(is_verified=True, is_staff=True)
        assert [r["id"] for r in _client(staff).get(reverse("objection-list")).data["results"]] == [objection_id]
        assert _respond(staff, objection_id).status_code == 200

    def test_answer_validated(self):
        _owner, teacher, classroom, student = _school_class()
        objection_id = _object(student, _work(student, classroom)).data["id"]
        assert _respond(teacher, objection_id, decision="maybe").status_code == 400
        assert _respond(teacher, objection_id, response="ok").status_code == 400

    def test_overdue_flag(self):
        _owner, teacher, classroom, student = _school_class()
        objection_id = _object(student, _work(student, classroom)).data["id"]
        VerdictObjection.objects.filter(id=objection_id).update(due_at=timezone.now() - timedelta(minutes=1))
        rows = _client(teacher).get(reverse("objection-list")).data["results"]
        assert rows[0]["overdue"] is True
        _respond(teacher, objection_id)
        rows = _client(teacher).get(reverse("objection-list")).data["results"]
        assert rows[0]["overdue"] is False


@pytest.mark.django_db
class TestDetailField:
    def test_detail_shows_objection_to_author_and_supervisor(self):
        _owner, teacher, classroom, student = _school_class()
        work = _work(student, classroom)
        url = reverse("submission-detail", kwargs={"id": work.id})
        assert _client(student).get(url).data["objection"] is None
        objection_id = _object(student, work).data["id"]
        for viewer in (student, teacher):
            payload = _client(viewer).get(url).data["objection"]
            assert payload["id"] == objection_id
            assert payload["submission_title"] == work.original_filename

    def test_detail_hides_objection_from_others(self):
        _owner, _teacher, classroom, student = _school_class()
        work = _work(student, classroom)
        _object(student, work)
        colleague = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=classroom.organization, user=colleague, role=OrgMember.Role.TEACHER)
        response = _client(colleague).get(reverse("submission-detail", kwargs={"id": work.id}))
        assert response.status_code == 404
        assert latest_objection_payload(work, colleague) is None
        assert latest_objection_payload(work, None) is None
        assert latest_objection_payload(work, UserFactory(is_staff=True))["submission_id"] == str(work.id)
