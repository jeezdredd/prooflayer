import json
from unittest.mock import patch

import pytest
from django.core import mail as outbox
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from api.changelog import SOURCE, draft_digest, load_source, sync
from api.models import ChangelogEntry
from users.models import ProductUpdate
from users.tests.factories import UserFactory


def test_source_entries_are_complete_and_unique():
    entries = load_source()
    slugs = [e["slug"] for e in entries]
    assert len(slugs) == len(set(slugs))
    for entry in entries:
        assert entry["kind"] in {"feature", "improvement", "fix"}
        for field in ("title", "body"):
            assert entry[field]["en"].strip() and entry[field]["ru"].strip()
            assert "—" not in entry[field]["en"] + entry[field]["ru"]


@pytest.mark.django_db
def test_sync_is_idempotent_and_updates(tmp_path):
    source = tmp_path / "changelog.json"
    item = {"slug": "x", "date": "2026-10-01", "kind": "fix", "title": {"en": "A", "ru": "А"}, "body": {"en": "b", "ru": "б"}}
    source.write_text(json.dumps([item]))
    assert sync(source) == (1, 0)
    item["title"]["en"] = "A2"
    source.write_text(json.dumps([item]))
    assert sync(source) == (0, 1)
    assert ChangelogEntry.objects.get(slug="x").title_en == "A2"


@pytest.mark.django_db
def test_digest_collects_pending_entries_once():
    sync(SOURCE)
    count = ChangelogEntry.objects.count()
    update = draft_digest()
    assert update.status == ProductUpdate.Status.DRAFT
    assert update.changelog_entries.count() == count
    assert "- " in update.body_en and "- " in update.body_ru
    assert update.cta_url.endswith("/changelog")
    assert draft_digest() is None


@pytest.mark.django_db
def test_changelog_endpoint_is_public_and_hides_unpublished():
    sync(SOURCE)
    hidden = ChangelogEntry.objects.first()
    hidden.is_published = False
    hidden.save()
    response = APIClient().get(reverse("system-changelog"))
    assert response.status_code == 200
    slugs = [e["slug"] for e in response.data["entries"]]
    assert hidden.slug not in slugs
    assert {"title_en", "title_ru", "body_en", "body_ru", "kind", "date"} <= set(response.data["entries"][0])


@pytest.mark.django_db
class TestEmailTest:
    def test_staff_only(self):
        client = APIClient()
        client.force_authenticate(UserFactory())
        assert client.get(reverse("email-test")).status_code == 403

    @override_settings(EMAIL_CONFIGURED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_sends_chosen_kind_to_self(self):
        staff = UserFactory(is_staff=True, language="ru")
        client = APIClient()
        client.force_authenticate(staff)
        response = client.post(reverse("email-test"), {"kind": "update"}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "sent"
        message = outbox.outbox[-1]
        assert message.to == [staff.email]
        assert message.subject.startswith("[Test] ")
        recent = client.get(reverse("email-test")).data["recent"]
        assert recent[0]["kind"] == "test"

    def test_unknown_kind_rejected(self):
        client = APIClient()
        client.force_authenticate(UserFactory(is_staff=True))
        assert client.post(reverse("email-test"), {"kind": "spam"}, format="json").status_code == 400

    def test_send_failure_reported(self):
        client = APIClient()
        client.force_authenticate(UserFactory(is_staff=True))
        with patch("users.mail.deliver", side_effect=RuntimeError("resend down")):
            response = client.post(reverse("email-test"), {"kind": "verify"}, format="json")
        assert response.status_code == 502
        assert "resend down" in response.data["error"]
