import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from api.models import RoadmapItem
from users.tests.factories import UserFactory

LIST = "roadmap-list"


def detail(item):
    return reverse("roadmap-detail", kwargs={"id": item.id})


@pytest.fixture
def items():
    RoadmapItem.objects.all().delete()
    shown = RoadmapItem.objects.create(title="Text detector v2", status="building", position=1)
    hidden = RoadmapItem.objects.create(title="Secret", status="exploring", position=2, is_published=False)
    return shown, hidden


@pytest.mark.django_db
class TestRoadmap:
    def test_public_sees_only_published(self, items):
        response = APIClient().get(reverse(LIST))
        assert response.status_code == 200
        assert [row["title"] for row in response.data] == ["Text detector v2"]

    def test_staff_sees_drafts(self, items):
        client = APIClient()
        client.force_authenticate(UserFactory(is_staff=True))
        assert [row["title"] for row in client.get(reverse(LIST)).data] == ["Text detector v2", "Secret"]

    def test_anonymous_and_regular_users_cannot_write(self, items):
        shown, _ = items
        assert APIClient().post(reverse(LIST), {"title": "x"}).status_code in (401, 403)
        client = APIClient()
        client.force_authenticate(UserFactory())
        assert client.patch(detail(shown), {"title": "hacked"}).status_code == 403
        assert client.delete(detail(shown)).status_code == 403
        shown.refresh_from_db()
        assert shown.title == "Text detector v2"

    def test_staff_creates_edits_and_deletes(self, items):
        shown, hidden = items
        client = APIClient()
        client.force_authenticate(UserFactory(is_staff=True))
        created = client.post(reverse(LIST), {"title": "LMS export", "body": "CSV to Moodle", "status": "beta", "eta": "Q1 2027"})
        assert created.status_code == 201
        assert client.patch(detail(shown), {"status": "beta", "is_published": False}, format="json").status_code == 200
        shown.refresh_from_db()
        assert (shown.status, shown.is_published) == ("beta", False)
        assert client.delete(detail(hidden)).status_code == 204
        assert set(RoadmapItem.objects.values_list("title", flat=True)) == {"Text detector v2", "LMS export"}

    def test_body_length_is_capped(self, items):
        client = APIClient()
        client.force_authenticate(UserFactory(is_staff=True))
        assert client.post(reverse(LIST), {"title": "Long", "body": "x" * 601}).status_code == 400


@pytest.mark.django_db
class TestOctoberRefresh:
    def test_roadmap_shows_only_upcoming_work(self):
        rows = RoadmapItem.objects.filter(is_published=True).order_by("position")
        published = list(rows.values_list("title", flat=True))
        assert "Text detector v2" not in published
        assert "Highlighted passages in essays" not in published
        assert published[:5] == [
            "Humanizer-proof text check", "Manipulation map", "Document forgery check", "Image history", "AI music check",
        ]
        assert all(RoadmapItem.objects.get(title=t).title_ru for t in published)
