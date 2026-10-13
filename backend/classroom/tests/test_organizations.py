import io
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from billing.models import Subscription, get_or_create_subscription, uploads_this_month
from classroom.models import Classroom, Membership, Organization, OrgMember
from content.models import Submission
from content.tests.factories import SubmissionFactory
from users.tests.factories import UserFactory


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _edu_user():
    user = UserFactory(is_verified=True)
    sub = get_or_create_subscription(user)
    sub.tier = Subscription.Tier.EDUCATION
    sub.save(update_fields=["tier"])
    return user


def _school():
    owner = _edu_user()
    org = Organization.create_for(owner, "Lyceum 239", "lyceum-239")
    return owner, org


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (5, 5, 5)).save(buf, format="JPEG")
    return SimpleUploadedFile("w.jpg", buf.getvalue(), content_type="image/jpeg")


@pytest.mark.django_db
class TestOrganizationCreate:
    def test_education_user_creates_and_becomes_admin(self):
        user = _edu_user()
        response = _client(user).post(reverse("org-list"), {"name": "Lyceum 239", "slug": "Lyceum-239"}, format="json")
        assert response.status_code == 201
        assert response.data["slug"] == "lyceum-239"
        assert response.data["role"] == "admin"
        assert len(response.data["teacher_code"]) == 8

    def test_free_user_gets_402(self):
        response = _client(UserFactory(is_verified=True)).post(reverse("org-list"), {"name": "x", "slug": "abc"}, format="json")
        assert response.status_code == 402

    @pytest.mark.parametrize("slug", ["ab", "-lead", "trail-", "Has Space", "admin", "login", "x" * 41])
    def test_bad_or_reserved_slug_rejected(self, slug):
        response = _client(_edu_user()).post(reverse("org-list"), {"name": "School", "slug": slug}, format="json")
        assert response.status_code == 400

    def test_taken_slug_rejected(self):
        _school()
        response = _client(_edu_user()).post(reverse("org-list"), {"name": "Copy", "slug": "lyceum-239"}, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestOrganizationPublicAndRoles:
    def test_anonymous_sees_name_only(self):
        _school()
        response = _client().get(reverse("org-detail", kwargs={"slug": "lyceum-239"}))
        assert response.status_code == 200
        assert response.data == {"name": "Lyceum 239", "slug": "lyceum-239", "role": None}

    def test_unknown_slug_404(self):
        assert _client().get(reverse("org-detail", kwargs={"slug": "nope-nope"})).status_code == 404

    def test_teacher_joins_with_code_without_own_plan(self):
        owner, org = _school()
        teacher = UserFactory(is_verified=True)
        response = _client(teacher).post(reverse("org-join-teacher", kwargs={"slug": org.slug}), {"code": org.teacher_code.lower()}, format="json")
        assert response.status_code == 201
        assert response.data["role"] == "teacher"
        assert "teacher_code" not in response.data
        created = _client(teacher).post(reverse("org-classes", kwargs={"slug": org.slug}), {"name": "9B"}, format="json")
        assert created.status_code == 201
        assert created.data["organization_slug"] == "lyceum-239"

    def test_wrong_teacher_code_404(self):
        _, org = _school()
        response = _client(UserFactory(is_verified=True)).post(reverse("org-join-teacher", kwargs={"slug": org.slug}), {"code": "WRONG123"}, format="json")
        assert response.status_code == 404

    def test_outsider_cannot_create_class_in_org(self):
        _, org = _school()
        response = _client(UserFactory(is_verified=True)).post(reverse("org-classes", kwargs={"slug": org.slug}), {"name": "x"}, format="json")
        assert response.status_code == 403

    def test_only_admin_rotates_code_and_lists_teachers(self):
        owner, org = _school()
        teacher = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=org, user=teacher)
        assert _client(teacher).post(reverse("org-rotate-code", kwargs={"slug": org.slug})).status_code == 403
        assert _client(teacher).get(reverse("org-teachers", kwargs={"slug": org.slug})).status_code == 403
        rotated = _client(owner).post(reverse("org-rotate-code", kwargs={"slug": org.slug}))
        assert rotated.status_code == 200 and rotated.data["teacher_code"] != org.teacher_code
        teachers = _client(owner).get(reverse("org-teachers", kwargs={"slug": org.slug})).data
        assert {t["role"] for t in teachers} == {"admin", "teacher"}

    def test_owner_cannot_be_removed(self):
        owner, org = _school()
        response = _client(owner).delete(reverse("org-teacher-detail", kwargs={"slug": org.slug, "user_id": owner.id}))
        assert response.status_code == 400


@pytest.mark.django_db
class TestOrgClassVisibility:
    def test_admin_sees_all_teacher_sees_own_student_sees_enrolled(self):
        owner, org = _school()
        teacher = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=org, user=teacher)
        mine = Classroom.create_for(teacher, "9B", organization=org)
        theirs = Classroom.create_for(owner, "10A", organization=org)
        student = UserFactory(is_verified=True)
        Membership.objects.create(classroom=mine, user=student)
        url = reverse("org-classes", kwargs={"slug": org.slug})
        assert {c["name"] for c in _client(owner).get(url).data} == {"9B", "10A"}
        assert [c["name"] for c in _client(teacher).get(url).data] == ["9B"]
        assert [c["name"] for c in _client(student).get(url).data] == ["9B"]
        assert _client(UserFactory(is_verified=True)).get(url).status_code == 404
        assert theirs.organization_id == org.id

    def test_hub_groups_everything(self):
        owner, org = _school()
        cls = Classroom.create_for(owner, "10A", organization=org)
        student = UserFactory(is_verified=True)
        Membership.objects.create(classroom=cls, user=student)
        hub = _client(student).get(reverse("classroom-hub")).data
        assert hub["organizations"] == []
        assert hub["enrolled"][0]["organization_slug"] == "lyceum-239"
        assert hub["can_create_organization"] is False
        assert _client(owner).get(reverse("classroom-hub")).data["organizations"][0]["role"] == "admin"


@pytest.mark.django_db
class TestAdminSupervision:
    def _setup(self):
        owner, org = _school()
        teacher = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=org, user=teacher, role=OrgMember.Role.TEACHER)
        cls = Classroom.create_for(teacher, "History", organization=org)
        student = UserFactory(is_verified=True)
        Membership.objects.create(classroom=cls, user=student)
        work = SubmissionFactory(user=student, classroom=cls)
        return owner, org, teacher, cls, student, work

    def test_admin_runs_any_class_of_the_school(self):
        owner, _, _, cls, student, work = self._setup()
        client = _client(owner)
        detail = client.get(reverse("classroom-detail", kwargs={"id": cls.id}))
        assert detail.status_code == 200
        assert detail.data["role"] == "teacher"
        assert detail.data["join_code"] == cls.join_code
        assert client.get(reverse("classroom-roster", kwargs={"id": cls.id})).data[0]["user_id"] == student.id
        assert client.get(reverse("classroom-stats", kwargs={"id": cls.id})).status_code == 200
        assert [row["id"] for row in client.get(reverse("classroom-submissions", kwargs={"id": cls.id})).data] == [str(work.id)]
        assert client.get(reverse("submission-detail", kwargs={"id": work.id})).status_code == 200

    def test_fellow_teacher_cannot_see_another_teachers_class(self):
        _, org, _, cls, _, work = self._setup()
        colleague = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=org, user=colleague, role=OrgMember.Role.TEACHER)
        client = _client(colleague)
        assert client.get(reverse("classroom-detail", kwargs={"id": cls.id})).status_code == 404
        assert client.get(reverse("submission-detail", kwargs={"id": work.id})).status_code == 404

    def test_admin_of_another_school_sees_nothing(self):
        _, _, _, cls, _, work = self._setup()
        other_owner = _edu_user()
        Organization.create_for(other_owner, "Other", "other-school")
        client = _client(other_owner)
        assert client.get(reverse("classroom-detail", kwargs={"id": cls.id})).status_code == 404
        assert client.get(reverse("submission-detail", kwargs={"id": work.id})).status_code == 404

    def test_admin_does_not_see_students_personal_uploads(self):
        owner, _, _, _, student, _ = self._setup()
        private = SubmissionFactory(user=student)
        assert _client(owner).get(reverse("submission-detail", kwargs={"id": private.id})).status_code == 404


@pytest.mark.django_db
@patch("content.intake.process_submission.delay")
class TestOrgBilling:
    def test_upload_into_org_class_charges_org_owner_not_teacher(self, _delay):
        owner, org = _school()
        teacher = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=org, user=teacher)
        cls = Classroom.create_for(teacher, "9B", organization=org)
        student = UserFactory(is_verified=True)
        Membership.objects.create(classroom=cls, user=student)
        response = _client(student).post(reverse("submission-list"), {"file": _jpeg(), "classroom": str(cls.id)}, format="multipart")
        assert response.status_code == 201
        assert uploads_this_month(owner) == 1
        assert uploads_this_month(teacher) == 0
        assert uploads_this_month(student) == 0

    def test_lapsed_org_plan_pauses_uploads_even_if_teacher_pays(self, _delay):
        owner, org = _school()
        teacher = _edu_user()
        OrgMember.objects.create(organization=org, user=teacher)
        cls = Classroom.create_for(teacher, "9B", organization=org)
        student = UserFactory(is_verified=True)
        Membership.objects.create(classroom=cls, user=student)
        sub = get_or_create_subscription(owner)
        sub.tier = Subscription.Tier.FREE
        sub.save(update_fields=["tier"])
        response = _client(student).post(reverse("submission-list"), {"file": _jpeg(), "classroom": str(cls.id)}, format="multipart")
        assert response.status_code == 403
        assert not Submission.objects.filter(classroom=cls).exists()
