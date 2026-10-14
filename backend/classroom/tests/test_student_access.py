import io
import json
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from billing.models import Subscription, get_or_create_subscription
from classroom.access import is_student_only
from classroom.models import Classroom, Membership, Organization, ShadowSet
from content.models import Submission
from users.models import User
from users.tests.factories import UserFactory


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (9, 9, 9)).save(buf, format="JPEG")
    return SimpleUploadedFile("work.jpg", buf.getvalue(), content_type="image/jpeg")


def _class_with_student():
    teacher = UserFactory(is_verified=True)
    sub = get_or_create_subscription(teacher)
    sub.tier = Subscription.Tier.EDUCATION
    sub.save(update_fields=["tier"])
    classroom = Classroom.create_for(teacher, "History 8A")
    student = UserFactory(is_verified=True)
    Membership.objects.create(classroom=classroom, user=student)
    return teacher, classroom, student


@pytest.mark.django_db
class TestStudentRole:
    def test_roles(self):
        teacher, _, student = _class_with_student()
        assert is_student_only(student)
        assert not is_student_only(teacher)
        assert not is_student_only(UserFactory(is_verified=True))

    def test_paid_or_staff_member_keeps_tools(self):
        _, classroom, student = _class_with_student()
        sub = get_or_create_subscription(student)
        sub.tier = Subscription.Tier.PRO
        sub.save(update_fields=["tier"])
        assert not is_student_only(student)
        staff = UserFactory(is_verified=True, is_staff=True)
        Membership.objects.create(classroom=classroom, user=staff)
        assert not is_student_only(staff)

    def test_me_reports_student_only(self):
        teacher, _, student = _class_with_student()
        assert _client(student).get(reverse("me")).data["student_only"] is True
        assert _client(teacher).get(reverse("me")).data["student_only"] is False


@pytest.mark.django_db
@patch("content.intake.process_submission.delay")
class TestStudentRestrictions:
    def test_student_hands_work_in_to_class(self, _delay):
        _, classroom, student = _class_with_student()
        response = _client(student).post(reverse("submission-list"), {"file": _jpeg(), "classroom": str(classroom.id)}, format="multipart")
        assert response.status_code == 201

    def test_student_cannot_upload_outside_class(self, _delay):
        _, _, student = _class_with_student()
        response = _client(student).post(reverse("submission-list"), {"file": _jpeg()}, format="multipart")
        assert response.status_code == 403
        assert response.data["code"] == "student_account"

    def test_student_cannot_use_tools(self, _delay):
        _, _, student = _class_with_student()
        client = _client(student)
        assert client.post(reverse("factcheck"), {"text": "The Earth is flat."}, format="json").status_code == 403
        assert client.get(reverse("public-feed")).status_code == 403
        assert client.post(reverse("batch-list"), {"files": [_jpeg()]}, format="multipart").status_code == 403
        assert client.post(reverse("vote-create"), {}, format="json").status_code == 403
        assert client.post(reverse("analyze-url"), {"url": "https://example.org/a.jpg"}, format="json").status_code == 403

    def test_student_sees_own_result_but_cannot_publish_or_rerun(self, _delay):
        _, classroom, student = _class_with_student()
        submission = Submission.objects.create(
            user=student, classroom=classroom, original_filename="w.txt", mime_type="text/plain", status=Submission.Status.COMPLETED
        )
        client = _client(student)
        assert client.get(reverse("submission-detail", kwargs={"id": submission.id})).status_code == 200
        assert client.post(reverse("submission-toggle-public", kwargs={"id": submission.id})).status_code == 403
        assert client.post(reverse("submission-reanalyze", kwargs={"id": submission.id})).status_code == 403

    def test_regular_user_keeps_tools(self, _delay):
        user = UserFactory(is_verified=True)
        assert _client(user).get(reverse("public-feed")).status_code == 200
        response = _client(user).post(reverse("submission-list"), {"file": _jpeg()}, format="multipart")
        assert response.status_code == 201


DEMO = {
    "organizations": [
        {
            "name": "Demo School",
            "slug": "demo-school-test",
            "teacher": {"email": "t@demo.prooflayer.cloud", "username": "demo_t", "first_name": "T", "last_name": "Teacher"},
            "classes": [
                {
                    "name": "8A",
                    "level": 8,
                    "shadow": {"prompt": "Why study history?", "language": "en", "answers": [{"variant": "grade 9", "text": "History matters."}]},
                    "students": [
                        {
                            "email": "s@demo.prooflayer.cloud",
                            "username": "demo_s",
                            "works": [
                                {"filename": "b.txt", "days_ago": 2, "text": "Second work."},
                                {"filename": "a.txt", "days_ago": 9, "text": "First work."},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
}


@pytest.mark.django_db
@patch("classroom.management.commands.seed_demo.sentence_vectors", return_value=[[0.1, 0.2]])
@patch("classroom.management.commands.seed_demo.process_submission.delay")
class TestSeedDemo:
    def _data(self, tmp_path, data=DEMO):
        path = tmp_path / "demo.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def test_creates_school_class_and_backdated_work(self, delay, _vectors, tmp_path):
        out = io.StringIO()
        call_command("seed_demo", "--data", self._data(tmp_path), "--no-wait", stdout=out)
        teacher = User.objects.get(email="t@demo.prooflayer.cloud")
        student = User.objects.get(email="s@demo.prooflayer.cloud")
        assert get_or_create_subscription(teacher).tier == Subscription.Tier.EDUCATION
        assert student.is_verified and student.terms_accepted_at and is_student_only(student)
        org = Organization.objects.get(slug="demo-school-test")
        classroom = Classroom.objects.get(organization=org)
        assert classroom.level == 8 and ShadowSet.objects.get(classroom=classroom).status == ShadowSet.Status.DONE
        works = list(Submission.objects.filter(user=student).order_by("created_at"))
        assert [w.original_filename for w in works] == ["a.txt", "b.txt"]
        assert delay.call_count == 2
        assert "s@demo.prooflayer.cloud" in out.getvalue()

    def test_refuses_to_duplicate_and_resets(self, _delay, _vectors, tmp_path):
        path = self._data(tmp_path)
        call_command("seed_demo", "--data", path, "--no-wait", stdout=io.StringIO())
        with pytest.raises(CommandError):
            call_command("seed_demo", "--data", path, "--no-wait", stdout=io.StringIO())
        call_command("seed_demo", "--data", path, "--no-wait", "--reset", stdout=io.StringIO())
        assert User.objects.filter(email__endswith="@demo.prooflayer.cloud").count() == 2
        assert Organization.objects.filter(slug="demo-school-test").count() == 1

    def test_orgs_filter(self, _delay, _vectors, tmp_path):
        with pytest.raises(CommandError):
            call_command("seed_demo", "--data", self._data(tmp_path), "--orgs", "missing", "--no-wait", stdout=io.StringIO())
        call_command("seed_demo", "--data", self._data(tmp_path), "--orgs", "demo-school-test", "--no-wait", stdout=io.StringIO())
        assert Organization.objects.filter(slug="demo-school-test").exists()

    def test_only_demo_domain_emails(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        data["organizations"][0]["teacher"]["email"] = "real.person@example.com"
        with pytest.raises(CommandError):
            call_command("seed_demo", "--data", self._data(tmp_path, data), "--no-wait", stdout=io.StringIO())
