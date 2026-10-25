import base64
import hashlib
import hmac
import io
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import F
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from billing.models import Subscription, get_or_create_subscription
from classroom.access import is_student_only
from classroom.management.commands.seed_demo import compare, demo_password
from classroom.models import Classroom, Membership, Organization, OrgMember, ShadowSet
from content.models import Batch, Submission, VerdictObjection
from content.tests.factories import SubmissionFactory
from plagiarism.models import PlagiarismReport
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


SHIPPED_DEMO = Path(__file__).resolve().parents[1] / "demo" / "demo_data.json"
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

    def test_files_teacher_uploads_and_objections(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        data["organizations"][0]["classes"][0]["students"][0]["works"] = [
            {"filename": "report.pdf", "days_ago": 3, "asset": "report.pdf", "uploaded_by_teacher": True,
             "objection": {"reason": "I wrote it myself.", "response": "We talked it through.", "decision": "upheld"}},
            {"filename": "essay.txt", "days_ago": 1, "text": "An essay.", "objection": {"reason": "This is my own work."}},
        ]
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "report.pdf").write_bytes(b"%PDF-1.4 demo")
        call_command("seed_demo", "--data", self._data(tmp_path, data), "--no-wait", stdout=io.StringIO())
        teacher = User.objects.get(email="t@demo.prooflayer.cloud")
        report = Submission.objects.get(original_filename="report.pdf")
        essay = Submission.objects.get(original_filename="essay.txt")
        assert report.mime_type == "application/pdf" and report.uploaded_by == teacher
        assert essay.mime_type == "text/plain" and essay.uploaded_by is None
        answered = VerdictObjection.objects.get(submission=report)
        assert answered.status == VerdictObjection.Status.ANSWERED and answered.responded_by == teacher
        assert answered.decision == VerdictObjection.Decision.UPHELD
        assert VerdictObjection.objects.get(submission=essay).status == VerdictObjection.Status.OPEN

    def test_school_staff_archive_batches_and_unlinked_checks(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        org = data["organizations"][0]
        org["teachers"] = [{"email": "t2@demo.prooflayer.cloud", "username": "demo_t2"}]
        works = org["classes"][0]["students"][0]["works"]
        works[0].update({"days_ago": 8, "batch": "Test sheet", "uploaded_by_teacher": True, "objection": {"reason": "Mine.", "days_ago": 6}})
        org["classes"][0]["teacher_checks"] = [{"filename": "sheet.txt", "days_ago": 1, "text": "No name on it."}]
        org["classes"].append({"name": "9B", "level": 9, "teacher": "demo_t2", "students": []})
        org["classes"].append({"name": "Old 8A", "archived": True, "students": []})
        call_command("seed_demo", "--data", self._data(tmp_path, data), "--no-wait", stdout=io.StringIO())
        owner = User.objects.get(email="t@demo.prooflayer.cloud")
        colleague = User.objects.get(email="t2@demo.prooflayer.cloud")
        school = Organization.objects.get(slug="demo-school-test")
        assert OrgMember.objects.get(organization=school, user=colleague).role == OrgMember.Role.TEACHER
        assert Classroom.objects.get(name="9B").owner == colleague
        assert Classroom.objects.get(name="Old 8A").archived and not Classroom.objects.get(name="8A").archived
        batched = Submission.objects.get(original_filename="b.txt")
        assert batched.batch.name == "Test sheet" and batched.batch.user == owner
        sheet = Submission.objects.get(original_filename="sheet.txt")
        assert sheet.user == owner and sheet.uploaded_by is None and sheet.classroom.name == "8A"
        overdue = VerdictObjection.objects.get(submission=batched)
        assert overdue.status == VerdictObjection.Status.OPEN and overdue.overdue

    def test_shipped_demo_data_assets_exist(self, _delay, _vectors):
        data = json.loads(SHIPPED_DEMO.read_text(encoding="utf-8"))
        assets = [w["asset"] for o in data["organizations"] for c in o["classes"] for s in c["students"] for w in s["works"] if w.get("asset")]
        assert assets and all((SHIPPED_DEMO.parent / "assets" / a).is_file() for a in assets)

    def test_only_demo_domain_emails(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        data["organizations"][0]["teacher"]["email"] = "real.person@example.com"
        with pytest.raises(CommandError):
            call_command("seed_demo", "--data", self._data(tmp_path, data), "--no-wait", stdout=io.StringIO())

    def test_passwords_come_from_the_secret_and_survive_a_reset(self, _delay, _vectors, tmp_path, monkeypatch):
        monkeypatch.setenv("DEMO_PASSWORD_SECRET", "demo-secret")
        path = self._data(tmp_path)
        out = io.StringIO()
        call_command("seed_demo", "--data", path, "--no-wait", stdout=out)
        expected = base64.urlsafe_b64encode(
            hmac.new(b"demo-secret", b"s@demo.prooflayer.cloud", hashlib.sha256).digest()
        ).decode("ascii")[:12]
        assert demo_password("s@demo.prooflayer.cloud", "demo-secret") == expected
        assert f"s@demo.prooflayer.cloud  {expected}" in out.getvalue()
        assert User.objects.get(email="s@demo.prooflayer.cloud").check_password(expected)
        call_command("seed_demo", "--data", path, "--no-wait", "--reset", stdout=io.StringIO())
        assert User.objects.get(email="s@demo.prooflayer.cloud").check_password(expected)

    def test_secret_key_is_the_default_secret(self, _delay, _vectors, tmp_path, monkeypatch, settings):
        monkeypatch.delenv("DEMO_PASSWORD_SECRET", raising=False)
        settings.SECRET_KEY = "server-secret-key"
        call_command("seed_demo", "--data", self._data(tmp_path), "--no-wait", stdout=io.StringIO())
        teacher = User.objects.get(email="t@demo.prooflayer.cloud")
        assert teacher.check_password(demo_password("t@demo.prooflayer.cloud", "server-secret-key"))

    def test_rotate_passwords_gives_random_ones(self, _delay, _vectors, tmp_path, monkeypatch):
        monkeypatch.setenv("DEMO_PASSWORD_SECRET", "demo-secret")
        out = io.StringIO()
        call_command("seed_demo", "--data", self._data(tmp_path), "--no-wait", "--rotate-passwords", stdout=out)
        student = User.objects.get(email="s@demo.prooflayer.cloud")
        assert not student.check_password(demo_password(student.email, "demo-secret"))
        printed = next(line.split()[-1] for line in out.getvalue().splitlines() if student.email in line)
        assert student.check_password(printed)
        assert "shown once" in out.getvalue()

    def test_objection_dated_before_its_work_is_refused(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        data["organizations"][0]["classes"][0]["students"][0]["works"][0]["objection"] = {"reason": "Mine.", "days_ago": 5}
        with pytest.raises(CommandError, match="dated before the work"):
            call_command("seed_demo", "--data", self._data(tmp_path, data), "--no-wait", stdout=io.StringIO())
        assert not User.objects.filter(email__endswith="@demo.prooflayer.cloud").exists()

    def test_answered_objection_follows_the_work(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        data["organizations"][0]["classes"][0]["students"][0]["works"][1]["objection"] = {
            "reason": "I wrote it myself.", "response": "We talked it through.", "decision": "upheld",
        }
        call_command("seed_demo", "--data", self._data(tmp_path, data), "--no-wait", stdout=io.StringIO())
        work = Submission.objects.get(original_filename="a.txt")
        objection = VerdictObjection.objects.get(submission=work)
        assert objection.created_at - work.created_at == timedelta(days=1)
        assert objection.responded_at - objection.created_at == timedelta(days=1)
        assert objection.due_at > objection.created_at

    def test_redate_moves_demo_dates_forward_without_touching_other_work(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        data["organizations"][0]["classes"][0]["students"][0]["works"][0].update(
            {"days_ago": 1, "batch": "Sheets", "objection": {"reason": "Mine.", "days_ago": 1}},
        )
        path = self._data(tmp_path, data)
        call_command("seed_demo", "--data", path, "--no-wait", stdout=io.StringIO())
        other = SubmissionFactory(user=UserFactory())
        other_created = other.created_at
        demo = Submission.objects.filter(user__email__endswith="@demo.prooflayer.cloud")
        before = dict(demo.values_list("original_filename", "created_at"))
        later = timedelta(days=20)
        demo.update(created_at=F("created_at") - later)
        VerdictObjection.objects.update(created_at=F("created_at") - later, due_at=F("due_at") - later)
        ShadowSet.objects.update(created_at=F("created_at") - later)
        Batch.objects.update(created_at=F("created_at") - later)
        shadow_before = ShadowSet.objects.get().created_at
        out = io.StringIO()
        call_command("seed_demo", "--data", path, "--redate", stdout=out)
        after = dict(demo.values_list("original_filename", "created_at"))
        assert "by 20 days" in out.getvalue()
        assert after["b.txt"] - after["a.txt"] == before["b.txt"] - before["a.txt"]
        assert abs((after["b.txt"] - before["b.txt"]).total_seconds()) < 5
        assert ShadowSet.objects.get().created_at - shadow_before == later
        assert Batch.objects.get().created_at == after["b.txt"]
        objection = VerdictObjection.objects.get()
        assert not objection.overdue and objection.created_at > after["b.txt"]
        other.refresh_from_db()
        assert other.created_at == other_created
        out = io.StringIO()
        call_command("seed_demo", "--data", path, "--redate", stdout=out)
        assert "already fresh" in out.getvalue()

    def test_redate_needs_a_seeded_demo(self, _delay, _vectors, tmp_path):
        with pytest.raises(CommandError, match="no demo to redate"):
            call_command("seed_demo", "--data", self._data(tmp_path), "--redate", stdout=io.StringIO())
        assert not User.objects.filter(email__endswith="@demo.prooflayer.cloud").exists()

    def test_verify_exits_with_an_error_when_the_demo_differs(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        works = data["organizations"][0]["classes"][0]["students"][0]["works"]
        works[0]["expect"] = {"verdict": ["fake"], "flags": ["ai_text"], "originality": [100, 100], "radar": []}
        works[1]["expect"] = {"verdict": ["authentic"], "flags": [], "originality": [100, 100], "radar": []}
        path = self._data(tmp_path, data)
        call_command("seed_demo", "--data", path, "--no-wait", stdout=io.StringIO())
        for work in Submission.objects.filter(user__email="s@demo.prooflayer.cloud"):
            Submission.objects.filter(pk=work.pk).update(status=Submission.Status.COMPLETED, final_verdict="authentic")
            PlagiarismReport.objects.create(submission=work, status=PlagiarismReport.Status.DONE, originality=100.0)
        out = io.StringIO()
        with pytest.raises(CommandError, match="does not show what demo_data.json expects"):
            call_command("seed_demo", "--data", path, "--verify", "--timeout", "0", stdout=out)
        table = out.getvalue()
        assert "verdict: expected fake, got authentic" in table
        assert "flags: expected ai_text, got none" in table
        assert "1 of 2 works differ" in table

    def test_verify_passes_when_the_demo_matches(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        for work in data["organizations"][0]["classes"][0]["students"][0]["works"]:
            work["expect"] = {"verdict": ["authentic"], "flags": [], "originality": [100, 100], "radar": []}
        path = self._data(tmp_path, data)
        call_command("seed_demo", "--data", path, "--no-wait", stdout=io.StringIO())
        for work in Submission.objects.filter(user__email="s@demo.prooflayer.cloud"):
            Submission.objects.filter(pk=work.pk).update(status=Submission.Status.COMPLETED, final_verdict="authentic")
            PlagiarismReport.objects.create(submission=work, status=PlagiarismReport.Status.DONE, originality=100.0)
        out = io.StringIO()
        call_command("seed_demo", "--data", path, "--verify", "--timeout", "0", stdout=out)
        assert "all 2 works show what demo_data.json expects" in out.getvalue()

    def test_unknown_expect_keys_are_refused(self, _delay, _vectors, tmp_path):
        data = json.loads(json.dumps(DEMO))
        data["organizations"][0]["classes"][0]["students"][0]["works"][0]["expect"] = {"flag": ["ai_text"]}
        with pytest.raises(CommandError, match="unknown expect keys"):
            call_command("seed_demo", "--data", self._data(tmp_path, data), "--no-wait", stdout=io.StringIO())


class TestDemoCompare:
    def test_matching_work_has_no_problems(self):
        actual = {"verdict": "authentic", "flags": [], "originality": 100.0, "web_status": "ok", "radar": []}
        assert compare({"verdict": ["authentic"], "flags": [], "originality": [100, 100], "radar": []}, actual) == []

    def test_originality_out_of_range_names_the_web_status(self):
        actual = {"verdict": "authentic", "flags": [], "originality": 100.0, "web_status": "failed", "radar": []}
        assert compare({"originality": [0, 59]}, actual) == ["originality: expected 0-59, got 100 (web search: failed)"]

    def test_picture_expects_no_originality_report(self):
        actual = {"verdict": "fake", "flags": ["ai_trace"], "originality": None, "web_status": None, "radar": []}
        assert compare({"verdict": ["fake"], "flags": ["ai_trace"], "originality": None}, actual) == []

    def test_flag_order_does_not_matter(self):
        actual = {"verdict": "suspicious", "flags": ["ai_text", "age"], "originality": 100.0, "web_status": "ok", "radar": ["ai"]}
        assert compare({"flags": ["age", "ai_text"], "radar": ["ai"]}, actual) == []
