import csv
import io
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from analyzers.models import AnalysisResult, AnalyzerConfig
from analyzers.tests.factories import AnalysisResultFactory, AnalyzerConfigFactory
from billing.models import Subscription, get_or_create_subscription
from classroom import shadow as shadow_module
from classroom.export import BOM
from classroom.models import Classroom, Membership, Organization, ShadowSet
from classroom.tasks import LLM_FAILED, NO_ANSWERS, build_shadow_set
from content.models import Batch, Submission, VerdictObjection
from content.tests.factories import SubmissionFactory
from plagiarism.models import PlagiarismReport
from users.tests.factories import UserFactory


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _teacher(**names):
    user = UserFactory(is_verified=True, **names)
    sub = get_or_create_subscription(user)
    sub.tier = Subscription.Tier.EDUCATION
    sub.save(update_fields=["tier"])
    return user


def _class():
    teacher = _teacher(first_name="Елена", last_name="Смирнова")
    classroom = Classroom.create_for(teacher, "8А")
    student = UserFactory(is_verified=True, first_name="Анна", last_name="Ковалёва")
    Membership.objects.create(classroom=classroom, user=student)
    return teacher, classroom, student


def _done(classroom, user, verdict="authentic", mime="text/plain", **extra):
    return SubmissionFactory(
        user=user, classroom=classroom, status=Submission.Status.COMPLETED, final_verdict=verdict, mime_type=mime, **extra,
    )


def _analyzer(name):
    return AnalyzerConfig.objects.filter(name=name).first() or AnalyzerConfigFactory(name=name)


def _result(submission, name, verdict, evidence=None):
    return AnalysisResultFactory(submission=submission, analyzer=_analyzer(name), verdict=verdict, evidence=evidence or {})


def _rows(client, classroom, **params):
    return client.get(reverse("classroom-submissions", kwargs={"id": classroom.id}), params).data


def _flagged_ids(client, classroom):
    return {r["id"] for r in _rows(client, classroom, verdict="flagged")}


@pytest.mark.django_db
class TestNames:
    def test_class_pages_show_names_not_logins(self):
        teacher, classroom, student = _class()
        SubmissionFactory(user=student, classroom=classroom, uploaded_by=teacher)
        client = _client(teacher)
        row = _rows(client, classroom)[0]
        assert row["student"] == "Анна Ковалёва" and row["uploaded_by"] == "Елена Смирнова"
        roster = client.get(reverse("classroom-roster", kwargs={"id": classroom.id})).data
        assert roster[0]["name"] == "Анна Ковалёва" and roster[0]["username"] == student.username
        detail = _client(student).get(reverse("classroom-detail", kwargs={"id": classroom.id})).data
        assert detail["owner_name"] == "Елена Смирнова"

    def test_teacher_check_without_student_is_marked(self):
        teacher, classroom, student = _class()
        sheet = SubmissionFactory(user=teacher, classroom=classroom)
        own = SubmissionFactory(user=student, classroom=classroom)
        rows = {r["id"]: r for r in _rows(_client(teacher), classroom)}
        assert rows[str(sheet.id)]["unattributed"] is True
        assert rows[str(own.id)]["unattributed"] is False

    def test_joining_with_a_name_saves_it(self):
        _, classroom, _ = _class()
        newcomer = UserFactory(is_verified=True)
        response = _client(newcomer).post(
            reverse("classroom-join"), {"code": classroom.join_code, "name": "  Мария   Петрова "}, format="json",
        )
        assert response.status_code == 201
        newcomer.refresh_from_db()
        assert (newcomer.first_name, newcomer.last_name) == ("Мария", "Петрова")
        assert _client(newcomer).get(reverse("classroom-hub")).data["my_name"] == "Мария Петрова"

    def test_teacher_gives_a_name_when_joining_a_school_or_creating_one(self):
        owner = _teacher()
        response = _client(owner).post(
            reverse("org-list"), {"name": "Лицей", "slug": "lyceum-7", "my_name": "Елена Смирнова"}, format="json",
        )
        assert response.status_code == 201 and response.data["my_name"] == "Елена Смирнова"
        org = Organization.objects.get(slug="lyceum-7")
        colleague = UserFactory(is_verified=True)
        joined = _client(colleague).post(
            reverse("org-join-teacher", kwargs={"slug": org.slug}), {"code": org.teacher_code, "name": "Игорь Орлов"}, format="json",
        )
        assert joined.status_code == 201
        teachers = _client(owner).get(reverse("org-teachers", kwargs={"slug": org.slug})).data
        assert {t["name"] for t in teachers} == {"Елена Смирнова", "Игорь Орлов"}

    def test_joining_without_a_name_keeps_the_old_one(self):
        _, classroom, student = _class()
        other = Classroom.create_for(_teacher(), "9Б")
        _client(student).post(reverse("classroom-join"), {"code": other.join_code}, format="json")
        student.refresh_from_db()
        assert student.first_name == "Анна"


@pytest.mark.django_db
class TestAttentionIsConsistent:
    def test_disguised_letters_count_even_when_the_verdict_is_unsure(self):
        teacher, classroom, student = _class()
        work = _done(classroom, student, verdict="inconclusive")
        _result(work, "text_evasion", AnalysisResult.Verdict.SUSPICIOUS)
        client = _client(teacher)
        assert _rows(client, classroom)[0]["flags"] == ["tricks"]
        assert _flagged_ids(client, classroom) == {str(work.id)}
        assert client.get(reverse("classroom-stats", kwargs={"id": classroom.id})).data["flagged"] == 1
        assert client.get(reverse("classroom-roster", kwargs={"id": classroom.id})).data[0]["flagged"] == 1

    def test_ai_trace_in_file_counts(self):
        teacher, classroom, student = _class()
        work = _done(classroom, student, mime="image/png")
        _result(work, "metadata", AnalysisResult.Verdict.AUTHENTIC, {"evasion": [], "ai_trace": [{"kind": "c2pa"}]})
        clean = _done(classroom, student, mime="image/png")
        _result(clean, "metadata", AnalysisResult.Verdict.AUTHENTIC, {"evasion": [], "ai_trace": []})
        assert _flagged_ids(_client(teacher), classroom) == {str(work.id)}

    def test_flagged_audio_gets_a_chip(self):
        teacher, classroom, student = _class()
        _done(classroom, student, verdict="likely_fake", mime="audio/mpeg")
        assert _rows(_client(teacher), classroom)[0]["flags"] == ["ai_media"]

    def test_unfinished_work_is_not_counted(self):
        teacher, classroom, student = _class()
        work = SubmissionFactory(user=student, classroom=classroom, status=Submission.Status.PROCESSING, mime_type="text/plain")
        PlagiarismReport.objects.create(submission=work, status=PlagiarismReport.Status.DONE, originality=10.0)
        assert _flagged_ids(_client(teacher), classroom) == set()

    def test_class_list_and_hub_show_attention_counts(self):
        teacher, classroom, student = _class()
        _done(classroom, student, verdict="fake")
        _done(classroom, student)
        work = _done(classroom, student)
        VerdictObjection.objects.create(submission=work, author=student, reason="Я писала сама, правда.")
        late = VerdictObjection.objects.create(submission=_done(classroom, student), author=student, reason="Я писала сама, правда.")
        VerdictObjection.objects.filter(pk=late.pk).update(due_at=timezone.now() - timedelta(hours=1))
        expected = {"needs_attention": 1, "open_objections": 2, "overdue_objections": 1}
        listed = _client(teacher).get(reverse("classroom-list")).data
        assert listed[0]["attention"] == expected
        hub = _client(teacher).get(reverse("classroom-hub")).data
        assert hub["personal_classes"][0]["attention"] == expected
        assert _client(student).get(reverse("classroom-hub")).data["enrolled"][0]["attention"] is None

    def test_school_row_sums_the_classes(self):
        owner = _teacher()
        org = Organization.create_for(owner, "Лицей", "lyceum-12")
        classroom = Classroom.create_for(owner, "8А", organization=org)
        student = UserFactory(is_verified=True)
        Membership.objects.create(classroom=classroom, user=student)
        _done(classroom, student, verdict="fake")
        hub = _client(owner).get(reverse("classroom-hub")).data
        assert hub["organizations"][0]["attention"]["needs_attention"] == 1
        classes = _client(owner).get(reverse("org-classes", kwargs={"slug": org.slug})).data
        assert classes[0]["attention"]["needs_attention"] == 1


@pytest.mark.django_db
class TestClearedWork:
    def _cleared(self):
        teacher, classroom, student = _class()
        work = _done(classroom, student, verdict="fake")
        _result(work, "text_classifier", AnalysisResult.Verdict.FAKE)
        PlagiarismReport.objects.create(submission=work, status=PlagiarismReport.Status.DONE, originality=70.0)
        objection = _client(student).post(
            reverse("submission-objection", kwargs={"id": work.id}), {"reason": "Я писала сама, могу пересказать."}, format="json",
        ).data
        response = _client(teacher).post(
            reverse("objection-respond", kwargs={"id": objection["id"]}),
            {"decision": "changed", "response": "Поговорили, работа своя."},
            format="json",
        )
        assert response.status_code == 200
        return teacher, classroom, student, work

    def test_cleared_work_drops_out_of_every_count(self):
        teacher, classroom, student, work = self._cleared()
        client = _client(teacher)
        row = _rows(client, classroom)[0]
        assert row["final_verdict"] == "authentic" and row["cleared"] is True and row["flags"] == []
        assert row["objection"]["status"] == "answered" and row["objection"]["decision"] == "changed"
        assert _flagged_ids(client, classroom) == set()
        assert client.get(reverse("classroom-stats", kwargs={"id": classroom.id})).data["flagged"] == 0
        assert client.get(reverse("classroom-roster", kwargs={"id": classroom.id})).data[0]["flagged"] == 0

    def test_student_row_shows_open_objection(self):
        teacher, classroom, student = _class()
        work = _done(classroom, student, verdict="fake")
        VerdictObjection.objects.create(submission=work, author=student, reason="Я писала сама, правда.")
        row = _rows(_client(student), classroom)[0]
        assert row["objection"]["status"] == "open" and row["objection"]["overdue"] is False
        assert row["cleared"] is False


@pytest.mark.django_db
class TestCsvExport:
    def test_russian_table_for_excel(self):
        teacher, classroom, student = _class()
        work = _done(classroom, student, verdict="fake", original_filename="Петр.txt")
        _result(work, "text_classifier", AnalysisResult.Verdict.FAKE)
        PlagiarismReport.objects.create(submission=work, status=PlagiarismReport.Status.DONE, originality=70.0)
        SubmissionFactory(user=teacher, classroom=classroom, status=Submission.Status.COMPLETED, final_verdict="authentic")
        response = _client(teacher).get(reverse("classroom-export-csv", kwargs={"id": classroom.id}), {"lang": "ru"})
        body = response.content.decode("utf-8")
        assert body.startswith(BOM)
        rows = list(csv.reader(io.StringIO(body[1:]), delimiter=";"))
        assert rows[0] == ["Ученик", "Работа", "Дата", "Итог", "Что нашли проверки", "Совпадения %", "Возражение"]
        by_name = {r[0]: r for r in rows[1:]}
        assert by_name["Анна Ковалёва"][1] == "Петр.txt"
        assert by_name["Анна Ковалёва"][3] == "Серьёзные признаки, что работу писал не ученик"
        assert by_name["Анна Ковалёва"][4] == "текст чат-бота, совпадения 30%"
        assert by_name["Анна Ковалёва"][5] == "30"
        assert "Без ученика (проверка учителя)" in by_name
        assert str(work.id) not in body

    def test_table_uses_the_class_page_wording_and_rounding(self):
        teacher, classroom, student = _class()
        work = _done(classroom, student, verdict="inconclusive", original_filename="Сочинение.txt")
        PlagiarismReport.objects.create(submission=work, status=PlagiarismReport.Status.DONE, originality=68.5)
        VerdictObjection.objects.create(
            submission=_done(classroom, student, verdict="authentic", original_filename="Эссе.txt"), author=student,
            reason="Я писала сама, правда.", status="answered", decision="changed", response="Поговорили, работа своя.",
        )
        response = _client(teacher).get(reverse("classroom-export-csv", kwargs={"id": classroom.id}), {"lang": "ru"})
        rows = {r[1]: r for r in csv.reader(io.StringIO(response.content.decode("utf-8")[1:]), delimiter=";")}
        assert rows["Сочинение.txt"][3] == "Часть текста совпадает с другими источниками, стоит посмотреть"
        assert rows["Сочинение.txt"][4] == "совпадения 31%" and rows["Сочинение.txt"][5] == "31"
        assert rows["Эссе.txt"][3] == "Учитель снял подозрение после возражения"
        assert rows["Эссе.txt"][6] == "подозрение снято"

    def test_english_table_by_default_for_english_accounts(self):
        teacher, classroom, student = _class()
        _done(classroom, student)
        body = _client(teacher).get(reverse("classroom-export-csv", kwargs={"id": classroom.id})).content.decode("utf-8")
        rows = list(csv.reader(io.StringIO(body[1:])))
        assert rows[0][0] == "Student" and rows[1][3] == "Looks like the student's own work"


@pytest.mark.django_db
class TestClassBatches:
    def _batch(self):
        teacher, classroom, student = _class()
        batch = Batch.objects.create(user=teacher, name="Контрольная 8А", classroom=classroom)
        _done(classroom, student, verdict="fake", batch=batch, uploaded_by=teacher)
        _done(classroom, student, batch=batch, uploaded_by=teacher)
        return teacher, classroom, student, batch

    def test_batch_page_names_students_and_counts_flags(self):
        teacher, classroom, _, batch = self._batch()
        data = _client(teacher).get(reverse("batch-detail", kwargs={"id": batch.id})).data
        assert {item["student"] for item in data["items"]} == {"Анна Ковалёва"}
        assert data["summary"]["flagged"] == 1
        assert data["classroom"] == {"id": str(classroom.id), "name": "8А", "organization_slug": None, "role": "teacher"}

    def test_teacher_lists_and_opens_a_students_batch(self):
        teacher, classroom, student = _class()
        batch = Batch.objects.create(user=student, name="", classroom=classroom)
        _done(classroom, student, batch=batch)
        listed = _client(teacher).get(reverse("classroom-batches", kwargs={"id": classroom.id})).data
        assert [(b["id"], b["total"], b["flagged"]) for b in listed] == [(str(batch.id), 1, 0)]
        assert _client(teacher).get(reverse("batch-detail", kwargs={"id": batch.id})).status_code == 200
        assert _client(UserFactory(is_verified=True)).get(reverse("batch-detail", kwargs={"id": batch.id})).status_code == 404
        assert _client(student).get(reverse("classroom-batches", kwargs={"id": classroom.id})).status_code == 403

    def test_own_batch_list_stays_own(self):
        teacher, classroom, student = _class()
        own = Batch.objects.create(user=teacher, name="Моя загрузка", classroom=classroom)
        Batch.objects.create(user=student, name="", classroom=classroom)
        listed = _client(teacher).get(reverse("batch-list")).data["results"]
        assert [b["id"] for b in listed] == [str(own.id)]

    def test_class_batch_csv_is_the_plain_table(self):
        teacher, _, _, batch = self._batch()
        body = _client(teacher).get(reverse("batch-export-csv", kwargs={"id": batch.id}), {"lang": "ru"}).content.decode()
        assert body.startswith(BOM) and "Анна Ковалёва" in body


@pytest.mark.django_db
class TestAiAnswers:
    def _set(self, classroom, days_ago):
        shadow = ShadowSet.objects.create(
            classroom=classroom, prompt="Нужно ли читать книги сегодня?", language="ru", status=ShadowSet.Status.DONE,
        )
        ShadowSet.objects.filter(pk=shadow.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        return shadow

    def test_failures_are_stored_as_codes(self):
        _, classroom, _ = _class()
        shadow = ShadowSet.objects.create(classroom=classroom, prompt="Нужно ли читать книги сегодня?", language="ru")
        with patch.object(shadow_module, "_generate", side_effect=ConnectionError("HTTPConnectionPool timeout")):
            build_shadow_set(str(shadow.id))
        shadow.refresh_from_db()
        assert shadow.error == NO_ANSWERS
        with patch("classroom.tasks.build", side_effect=RuntimeError("boom")):
            build_shadow_set(str(shadow.id))
        shadow.refresh_from_db()
        assert shadow.error == LLM_FAILED

    def test_list_says_which_works_matched_and_how_many_were_compared(self):
        teacher, classroom, student = _class()
        shadow = self._set(classroom, days_ago=5)
        before = _done(classroom, student)
        Submission.objects.filter(pk=before.pk).update(created_at=timezone.now() - timedelta(days=9))
        _result(before, "text_shadow", AnalysisResult.Verdict.INCONCLUSIVE, {"share": 0.1})
        matched = _done(classroom, student, original_filename="Книги.txt")
        _result(matched, "text_shadow", AnalysisResult.Verdict.SUSPICIOUS, {"share": 0.8, "shadow_set": str(shadow.id)})
        clean = _done(classroom, student)
        _result(clean, "text_shadow", AnalysisResult.Verdict.INCONCLUSIVE, {"share": 0.1, "shadow_set": str(shadow.id)})
        data = _client(teacher).get(reverse("classroom-shadows", kwargs={"id": classroom.id})).data
        assert data[0]["compared"] == 2
        assert data[0]["matched"] == [{"submission_id": str(matched.id), "student": "Анна Ковалёва", "filename": "Книги.txt"}]


@pytest.mark.django_db
class TestObjectionAnswerEmail:
    def test_student_gets_the_answer_with_a_classroom_link(self, settings, django_capture_on_commit_callbacks):
        settings.CLASSROOM_URL = "https://classroom.example"
        teacher, classroom, student = _class()
        student.language = "ru"
        student.save(update_fields=["language"])
        work = _done(classroom, student, verdict="fake")
        objection = VerdictObjection.objects.create(submission=work, author=student, reason="Я писала сама, правда.")
        with django_capture_on_commit_callbacks(execute=True):
            response = _client(teacher).post(
                reverse("objection-respond", kwargs={"id": objection.id}),
                {"decision": "upheld", "response": "Поговорили, вывод остаётся."},
                format="json",
            )
        assert response.status_code == 200
        sent = [m for m in mail.outbox if m.to == [student.email]]
        assert len(sent) == 1
        assert f"https://classroom.example/results/{work.id}" in sent[0].body
        assert "Вердикт оставлен без изменений" in sent[0].body
        assert "Поговорили, вывод остаётся." in sent[0].body
