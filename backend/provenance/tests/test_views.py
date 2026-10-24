import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from classroom.models import Classroom, Membership, Organization, OrgMember
from content.tests.factories import SubmissionFactory
from provenance.models import ProvenanceResult
from users.tests.factories import UserFactory


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _url(submission_id):
    return reverse("provenance-list", kwargs={"submission_id": submission_id})


def _phash_match(submission, other, distance=2, title=""):
    return ProvenanceResult.objects.create(
        submission=submission,
        source_type=ProvenanceResult.SourceType.PHASH_MATCH,
        title=title,
        similarity_score=round(1 - distance / 64, 4),
        raw_data={"submission_id": str(other.id), "distance": distance},
    )


def _school():
    owner = UserFactory(is_verified=True)
    org = Organization.create_for(owner, "Lyceum 239", "lyceum-239")
    teacher = UserFactory(is_verified=True, first_name="Анна", last_name="Петрова")
    OrgMember.objects.create(organization=org, user=teacher, role=OrgMember.Role.TEACHER)
    classroom = Classroom.create_for(teacher, "9Б", organization=org)
    olga = UserFactory(is_verified=True, first_name="Ольга", last_name="Смирнова")
    polina = UserFactory(is_verified=True, first_name="Полина", last_name="Новикова")
    for student in (olga, polina):
        Membership.objects.create(classroom=classroom, user=student)
    return org, teacher, classroom, olga, polina


@pytest.mark.django_db
class TestProvenanceListView:
    def setup_method(self):
        self.user = UserFactory()
        self.client = _client(self.user)

    def test_unauthenticated_returns_401(self):
        submission = SubmissionFactory(user=self.user)
        assert APIClient().get(_url(submission.id)).status_code == 401

    def test_empty_list_when_no_results(self):
        submission = SubmissionFactory(user=self.user)
        response = self.client.get(_url(submission.id))
        assert response.status_code == 200
        assert response.data == []

    def test_own_earlier_upload_is_named(self):
        submission = SubmissionFactory(user=self.user)
        earlier = SubmissionFactory(user=self.user, original_filename="match.jpg")
        _phash_match(submission, earlier)
        response = self.client.get(_url(submission.id))
        assert response.status_code == 200
        assert len(response.data) == 1
        item = response.data[0]
        assert item["title"] == "match.jpg"
        assert item["match"]["scope"] == "yours"
        assert item["match"]["kind"] == "same"
        assert item["match"]["submission_id"] == str(earlier.id)

    def test_other_users_work_returns_404(self):
        submission = SubmissionFactory(user=UserFactory())
        ProvenanceResult.objects.create(
            submission=submission, source_type=ProvenanceResult.SourceType.TINEYE, title="secret.jpg",
        )
        assert self.client.get(_url(submission.id)).status_code == 404

    def test_stored_file_name_of_a_hidden_work_is_not_shown(self):
        submission = SubmissionFactory(user=self.user)
        stranger = SubmissionFactory(original_filename="someone-else.jpg")
        _phash_match(submission, stranger, title="someone-else.jpg")
        response = self.client.get(_url(submission.id))
        body = response.content.decode()
        assert "someone-else.jpg" not in body
        assert str(stranger.id) not in body
        assert response.data[0]["match"]["scope"] == "elsewhere"
        assert response.data[0]["match"]["author"] is None

    def test_near_and_similar_kinds(self):
        submission = SubmissionFactory(user=self.user)
        near = SubmissionFactory(user=self.user)
        similar = SubmissionFactory(user=self.user)
        _phash_match(submission, near, distance=12)
        ProvenanceResult.objects.create(
            submission=submission,
            source_type=ProvenanceResult.SourceType.CLIP_NEIGHBOUR,
            similarity_score=0.9,
            raw_data={"submission_id": str(similar.id), "cosine_distance": 0.1},
        )
        kinds = {item["match"]["submission_id"]: item["match"]["kind"] for item in self.client.get(_url(submission.id)).data}
        assert kinds == {str(near.id): "near", str(similar.id): "similar"}

    def test_external_rows_keep_their_link(self):
        submission = SubmissionFactory(user=self.user)
        ProvenanceResult.objects.create(
            submission=submission,
            source_type=ProvenanceResult.SourceType.TINEYE,
            source_url="https://example.com/a.jpg",
            title="Stock archive",
            similarity_score=0.88,
        )
        item = self.client.get(_url(submission.id)).data[0]
        assert item["source_url"] == "https://example.com/a.jpg"
        assert item["match"] is None


@pytest.mark.django_db
class TestClassProvenance:
    def test_teacher_sees_which_student_handed_in_the_same_picture(self):
        _org, teacher, classroom, olga, polina = _school()
        first = SubmissionFactory(user=olga, classroom=classroom)
        second = SubmissionFactory(user=polina, classroom=classroom)
        _phash_match(second, first, distance=0)
        response = _client(teacher).get(_url(second.id))
        assert response.status_code == 200
        match = response.data[0]["match"]
        assert match["scope"] == "visible"
        assert match["author"] == "Ольга Смирнова"
        assert match["classroom"] == "9Б"
        assert match["submission_id"] == str(first.id)

    def test_earlier_work_also_shows_the_later_copy(self):
        _org, teacher, classroom, olga, polina = _school()
        first = SubmissionFactory(user=olga, classroom=classroom)
        second = SubmissionFactory(user=polina, classroom=classroom)
        _phash_match(second, first, distance=0)
        match = _client(teacher).get(_url(first.id)).data[0]["match"]
        assert match["author"] == "Полина Новикова"
        assert match["submission_id"] == str(second.id)

    def test_student_learns_only_that_a_classmate_handed_it_in(self):
        _org, _teacher, classroom, olga, polina = _school()
        first = SubmissionFactory(user=olga, classroom=classroom)
        second = SubmissionFactory(user=polina, classroom=classroom)
        _phash_match(second, first, distance=0)
        response = _client(polina).get(_url(second.id))
        assert response.status_code == 200
        match = response.data[0]["match"]
        assert match["scope"] == "same_class"
        assert match["author"] is None and match["submission_id"] is None
        assert "Ольга" not in response.content.decode()

    def test_other_class_of_the_school_stays_anonymous(self):
        org, teacher, classroom, olga, _polina = _school()
        colleague = UserFactory(is_verified=True)
        OrgMember.objects.create(organization=org, user=colleague, role=OrgMember.Role.TEACHER)
        other_class = Classroom.create_for(colleague, "10А", organization=org)
        stranger = UserFactory(is_verified=True, first_name="Иван", last_name="Иванов")
        Membership.objects.create(classroom=other_class, user=stranger)
        work = SubmissionFactory(user=olga, classroom=classroom)
        theirs = SubmissionFactory(user=stranger, classroom=other_class)
        _phash_match(work, theirs, distance=0)
        response = _client(teacher).get(_url(work.id))
        match = response.data[0]["match"]
        assert match["scope"] == "same_school"
        assert "Иван" not in response.content.decode()

    def test_unrelated_teacher_gets_404(self):
        _org, _teacher, classroom, olga, _polina = _school()
        work = SubmissionFactory(user=olga, classroom=classroom)
        assert _client(UserFactory(is_verified=True)).get(_url(work.id)).status_code == 404
