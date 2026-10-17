import io
from unittest.mock import patch

import docx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from analyzers.models import AnalysisResult
from analyzers.tests.factories import AnalysisResultFactory, AnalyzerConfigFactory
from billing.models import Subscription, get_or_create_subscription, uploads_this_month
from billing.plans import PLANS
from classroom.models import JOIN_CODE_LENGTH, Classroom, Membership
from common.documents import DOCX_MIME, document_stats, extract_text
from content.models import Submission
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _teacher():
    user = UserFactory(is_verified=True)
    sub = get_or_create_subscription(user)
    sub.tier = Subscription.Tier.EDUCATION
    sub.save(update_fields=["tier"])
    return user


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (9, 9, 9)).save(buf, format="JPEG")
    return SimpleUploadedFile("work.jpg", buf.getvalue(), content_type="image/jpeg")


def _docx_bytes(text):
    document = docx.Document()
    document.add_paragraph(text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _class_with_student():
    teacher = _teacher()
    classroom = Classroom.create_for(teacher, "Media literacy")
    student = UserFactory(is_verified=True)
    Membership.objects.create(classroom=classroom, user=student)
    return teacher, classroom, student


@pytest.mark.django_db
class TestCreateAndJoin:
    def test_free_user_cannot_create(self):
        response = _client(UserFactory(is_verified=True)).post(reverse("classroom-list"), {"name": "x"}, format="json")
        assert response.status_code == 402

    def test_pro_user_cannot_create(self):
        user = UserFactory(is_verified=True)
        sub = get_or_create_subscription(user)
        sub.tier = Subscription.Tier.PRO
        sub.save(update_fields=["tier"])
        response = _client(user).post(reverse("classroom-list"), {"name": "x"}, format="json")
        assert response.status_code == 402

    def test_education_teacher_creates_and_sees_code(self):
        response = _client(_teacher()).post(reverse("classroom-list"), {"name": "Year 10"}, format="json")
        assert response.status_code == 201
        assert response.data["role"] == "teacher"
        assert len(response.data["join_code"]) == JOIN_CODE_LENGTH

    def test_student_joins_by_code_case_insensitive_and_does_not_see_code(self):
        teacher = _teacher()
        classroom = Classroom.create_for(teacher, "Year 10")
        student = UserFactory(is_verified=True)
        response = _client(student).post(reverse("classroom-join"), {"code": classroom.join_code.lower()}, format="json")
        assert response.status_code == 201
        assert response.data["role"] == "student"
        assert response.data["join_code"] is None
        again = _client(student).post(reverse("classroom-join"), {"code": classroom.join_code}, format="json")
        assert again.status_code == 200
        assert Membership.objects.filter(classroom=classroom).count() == 1

    def test_wrong_or_archived_code_404(self):
        teacher = _teacher()
        classroom = Classroom.create_for(teacher, "Old")
        classroom.archived = True
        classroom.save(update_fields=["archived"])
        student = _client(UserFactory(is_verified=True))
        assert student.post(reverse("classroom-join"), {"code": classroom.join_code}, format="json").status_code == 404
        assert student.post(reverse("classroom-join"), {"code": "NOPE1234"}, format="json").status_code == 404

    def test_rotate_code_invalidates_old(self):
        teacher, classroom, _ = _class_with_student()
        old = classroom.join_code
        response = _client(teacher).post(reverse("classroom-rotate-code", kwargs={"id": classroom.id}))
        assert response.status_code == 200 and response.data["join_code"] != old
        late = _client(UserFactory(is_verified=True)).post(reverse("classroom-join"), {"code": old}, format="json")
        assert late.status_code == 404

    def test_student_cannot_rotate_or_see_roster(self):
        _, classroom, student = _class_with_student()
        client = _client(student)
        assert client.post(reverse("classroom-rotate-code", kwargs={"id": classroom.id})).status_code == 403
        assert client.get(reverse("classroom-roster", kwargs={"id": classroom.id})).status_code == 403
        assert client.get(reverse("classroom-stats", kwargs={"id": classroom.id})).status_code == 403

    def test_outsider_gets_404(self):
        _, classroom, _ = _class_with_student()
        response = _client(UserFactory(is_verified=True)).get(reverse("classroom-detail", kwargs={"id": classroom.id}))
        assert response.status_code == 404


@pytest.mark.django_db
@patch("content.intake.process_submission.delay")
class TestClassUploads:
    def test_student_upload_into_class_is_charged_to_teacher(self, _delay):
        teacher, classroom, student = _class_with_student()
        response = _client(student).post(
            reverse("submission-list"), {"file": _jpeg(), "classroom": str(classroom.id)}, format="multipart"
        )
        assert response.status_code == 201
        sub = Submission.objects.get(id=response.data["id"])
        assert sub.classroom_id == classroom.id and sub.user_id == student.id
        assert uploads_this_month(teacher) == 1
        assert uploads_this_month(student) == 0

    def test_teacher_quota_exhausted_blocks_student(self, _delay):
        _, classroom, student = _class_with_student()
        with patch("content.intake.uploads_this_month", return_value=PLANS["education"].uploads_per_month):
            response = _client(student).post(
                reverse("submission-list"), {"file": _jpeg(), "classroom": str(classroom.id)}, format="multipart"
            )
        assert response.status_code == 402

    def test_lapsed_teacher_plan_pauses_class(self, _delay):
        teacher, classroom, student = _class_with_student()
        sub = get_or_create_subscription(teacher)
        sub.tier = Subscription.Tier.FREE
        sub.save(update_fields=["tier"])
        response = _client(student).post(
            reverse("submission-list"), {"file": _jpeg(), "classroom": str(classroom.id)}, format="multipart"
        )
        assert response.status_code == 403

    def test_non_member_cannot_upload_into_class(self, _delay):
        _, classroom, _ = _class_with_student()
        response = _client(UserFactory(is_verified=True)).post(
            reverse("submission-list"), {"file": _jpeg(), "classroom": str(classroom.id)}, format="multipart"
        )
        assert response.status_code == 404

    def test_batch_into_class(self, _delay):
        teacher, classroom, student = _class_with_student()
        response = _client(student).post(
            reverse("batch-list"), {"files": [_jpeg(), _jpeg()], "classroom": str(classroom.id)}, format="multipart"
        )
        assert response.status_code == 201
        assert Submission.objects.filter(classroom=classroom, user=student).count() == 2
        assert uploads_this_month(teacher) == 2

    def test_docx_essay_is_accepted(self, _delay):
        _, classroom, student = _class_with_student()
        essay = SimpleUploadedFile("essay.docx", _docx_bytes("My essay about rivers."), content_type=DOCX_MIME)
        response = _client(student).post(
            reverse("submission-list"), {"file": essay, "classroom": str(classroom.id)}, format="multipart"
        )
        assert response.status_code == 201
        assert Submission.objects.get(id=response.data["id"]).mime_type == DOCX_MIME


@pytest.mark.django_db
class TestVisibility:
    def test_teacher_sees_class_work_not_private_work(self):
        teacher, classroom, student = _class_with_student()
        class_sub = SubmissionFactory(user=student, classroom=classroom)
        private_sub = SubmissionFactory(user=student)
        client = _client(teacher)
        assert client.get(reverse("submission-detail", kwargs={"id": class_sub.id})).status_code == 200
        assert client.get(reverse("submission-detail", kwargs={"id": private_sub.id})).status_code == 404
        listed = client.get(reverse("classroom-submissions", kwargs={"id": classroom.id})).data
        assert [row["id"] for row in listed] == [str(class_sub.id)]

    def test_class_list_names_the_checks_that_fired(self):
        teacher, classroom, student = _class_with_student()
        sub = SubmissionFactory(user=student, classroom=classroom, status=Submission.Status.COMPLETED, final_verdict="suspicious", mime_type="text/plain")
        AnalysisResultFactory(
            submission=sub, analyzer=AnalyzerConfigFactory(name="text_evasion"), verdict=AnalysisResult.Verdict.FAKE, confidence=0.9,
            evidence={"hidden_characters": 120},
        )
        AnalysisResultFactory(
            submission=sub, analyzer=AnalyzerConfigFactory(name="text_classifier"), verdict=AnalysisResult.Verdict.SUSPICIOUS, confidence=0.8,
            evidence={"ai_probability": 0.81},
        )
        AnalysisResultFactory(
            submission=sub, analyzer=AnalyzerConfigFactory(name="text_style"), verdict=AnalysisResult.Verdict.AUTHENTIC, confidence=0.5, evidence={},
        )
        rows = _client(teacher).get(reverse("classroom-submissions", kwargs={"id": classroom.id})).data
        assert rows[0]["flags"] == ["ai_text", "hidden_text"]

    def test_teacher_dashboard_list_excludes_student_work(self):
        teacher, classroom, student = _class_with_student()
        SubmissionFactory(user=student, classroom=classroom)
        response = _client(teacher).get(reverse("submission-list"))
        assert response.data["count"] == 0

    def test_student_sees_only_own_class_work(self):
        teacher, classroom, student = _class_with_student()
        other = UserFactory(is_verified=True)
        Membership.objects.create(classroom=classroom, user=other)
        mine = SubmissionFactory(user=student, classroom=classroom)
        theirs = SubmissionFactory(user=other, classroom=classroom)
        client = _client(student)
        rows = client.get(reverse("classroom-submissions", kwargs={"id": classroom.id})).data
        assert [row["id"] for row in rows] == [str(mine.id)]
        assert client.get(reverse("submission-detail", kwargs={"id": theirs.id})).status_code == 404

    def test_teacher_cannot_delete_or_publish_student_work(self):
        teacher, classroom, student = _class_with_student()
        sub = SubmissionFactory(user=student, classroom=classroom, status=Submission.Status.COMPLETED)
        client = _client(teacher)
        assert client.delete(reverse("submission-detail", kwargs={"id": sub.id})).status_code == 403
        assert client.post(reverse("submission-toggle-public", kwargs={"id": sub.id})).status_code == 403
        assert Submission.objects.filter(id=sub.id).exists()

    def test_removed_student_keeps_history_but_cannot_upload(self):
        teacher, classroom, student = _class_with_student()
        response = _client(teacher).delete(
            reverse("classroom-remove-member", kwargs={"id": classroom.id, "user_id": student.id})
        )
        assert response.status_code == 204
        assert not Membership.objects.filter(classroom=classroom, user=student).exists()


@pytest.mark.django_db
class TestTeacherViews:
    def test_roster_counts_and_stats(self):
        teacher, classroom, student = _class_with_student()
        SubmissionFactory(user=student, classroom=classroom, status=Submission.Status.COMPLETED, final_verdict="fake")
        SubmissionFactory(user=student, classroom=classroom, status=Submission.Status.COMPLETED, final_verdict="authentic")
        SubmissionFactory(user=student, status=Submission.Status.COMPLETED, final_verdict="fake")
        client = _client(teacher)
        roster = client.get(reverse("classroom-roster", kwargs={"id": classroom.id})).data
        assert roster[0]["total"] == 2 and roster[0]["flagged"] == 1
        stats = client.get(reverse("classroom-stats", kwargs={"id": classroom.id})).data
        assert stats["total"] == 2 and stats["flagged"] == 1 and stats["flagged_share"] == 0.5
        assert stats["by_verdict"] == {"fake": 1, "authentic": 1}
        flagged = client.get(reverse("classroom-submissions", kwargs={"id": classroom.id}), {"verdict": "flagged"}).data
        assert len(flagged) == 1

    def test_export_csv_guards_formulas(self):
        teacher, classroom, student = _class_with_student()
        student.username = "=evil"
        student.save(update_fields=["username"])
        SubmissionFactory(user=student, classroom=classroom)
        response = _client(teacher).get(reverse("classroom-export-csv", kwargs={"id": classroom.id}))
        assert response.status_code == 200
        assert "'=evil" in response.content.decode()


class TestDocuments:
    def test_docx_text_and_stats(self):
        text = extract_text(_docx_bytes("one two three"), DOCX_MIME)
        assert "one two three" in text
        assert document_stats(text)["words"] == 3


@pytest.mark.django_db
@patch("content.intake.process_submission.delay")
class TestTeacherUploadsForStudent:
    def test_teacher_checks_work_on_behalf_of_student(self, _delay):
        teacher, classroom, student = _class_with_student()
        response = _client(teacher).post(
            reverse("submission-list"),
            {"file": _jpeg(), "classroom": str(classroom.id), "student": str(student.id)},
            format="multipart",
        )
        assert response.status_code == 201
        sub = Submission.objects.get(id=response.data["id"])
        assert sub.user_id == student.id and sub.uploaded_by_id == teacher.id and sub.classroom_id == classroom.id
        assert uploads_this_month(teacher) == 1
        listed = _client(teacher).get(reverse("classroom-submissions", kwargs={"id": classroom.id})).data
        assert listed[0]["student_id"] == student.id and listed[0]["uploaded_by"] == teacher.username
        assert _client(student).get(reverse("submission-detail", kwargs={"id": sub.id})).status_code == 200

    def test_teacher_upload_without_student_stays_with_teacher(self, _delay):
        teacher, classroom, _ = _class_with_student()
        response = _client(teacher).post(
            reverse("submission-list"), {"file": _jpeg(), "classroom": str(classroom.id)}, format="multipart"
        )
        sub = Submission.objects.get(id=response.data["id"])
        assert sub.user_id == teacher.id and sub.uploaded_by_id is None

    def test_student_cannot_upload_for_classmate(self, _delay):
        _, classroom, student = _class_with_student()
        classmate = UserFactory(is_verified=True)
        Membership.objects.create(classroom=classroom, user=classmate)
        response = _client(student).post(
            reverse("submission-list"),
            {"file": _jpeg(), "classroom": str(classroom.id), "student": str(classmate.id)},
            format="multipart",
        )
        assert response.status_code == 403
        assert not Submission.objects.filter(user=classmate).exists()

    def test_teacher_cannot_assign_work_to_outsider(self, _delay):
        teacher, classroom, _ = _class_with_student()
        outsider = UserFactory(is_verified=True)
        response = _client(teacher).post(
            reverse("submission-list"),
            {"file": _jpeg(), "classroom": str(classroom.id), "student": str(outsider.id)},
            format="multipart",
        )
        assert response.status_code == 400
        assert not Submission.objects.filter(user=outsider).exists()

    def test_student_without_class_is_rejected(self, _delay):
        teacher, _, student = _class_with_student()
        response = _client(teacher).post(
            reverse("submission-list"), {"file": _jpeg(), "student": str(student.id)}, format="multipart"
        )
        assert response.status_code == 403

    def test_teacher_batch_for_student(self, _delay):
        teacher, classroom, student = _class_with_student()
        response = _client(teacher).post(
            reverse("batch-list"),
            {"files": [_jpeg(), _jpeg()], "classroom": str(classroom.id), "student": str(student.id)},
            format="multipart",
        )
        assert response.status_code == 201
        subs = Submission.objects.filter(batch_id=response.data["id"])
        assert subs.count() == 2
        assert set(subs.values_list("user_id", "uploaded_by_id")) == {(student.id, teacher.id)}
