import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Subscription, get_or_create_subscription
from common.url_safety import UnsafeUrlError
from content.models import Submission
from content.tests.factories import SubmissionFactory
from analyzers.tasks import aggregate_verdicts
from analyzers.tests.factories import AnalysisResultFactory, AnalyzerConfigFactory
from users.models import ApiKey
from users.tasks import deliver_submission_webhook
from users.webhooks import SIGNATURE_HEADER, TIMESTAMP_HEADER, build_payload, encode, sign

from .factories import UserFactory

PUBLIC = ["93.184.216.34"]


def _pro_user(**kwargs):
    user = UserFactory(is_verified=True, **kwargs)
    sub = get_or_create_subscription(user)
    sub.tier = Subscription.Tier.PRO
    sub.save(update_fields=["tier"])
    return user


def _session(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestKeyManagement:
    def test_free_user_cannot_create_keys(self):
        user = UserFactory(is_verified=True)
        response = _session(user).post(reverse("api-key-list"), {"name": "ci"}, format="json")
        assert response.status_code == 402

    def test_create_returns_raw_key_once_and_stores_only_hash(self):
        user = _pro_user()
        response = _session(user).post(reverse("api-key-list"), {"name": "ci"}, format="json")
        assert response.status_code == 201
        raw = response.data["key"]
        assert raw.startswith("pl_")
        stored = ApiKey.objects.get(id=response.data["id"])
        assert stored.key_hash == hashlib.sha256(raw.encode()).hexdigest()
        assert raw not in json.dumps(_session(user).get(reverse("api-key-list")).data, default=str)

    @patch("common.url_safety._dns_lookup", return_value=PUBLIC)
    def test_webhook_gets_secret(self, _dns):
        user = _pro_user()
        response = _session(user).post(
            reverse("api-key-list"), {"name": "hook", "webhook_url": "https://example.com/hook"}, format="json"
        )
        assert response.status_code == 201
        assert response.data["webhook_secret"].startswith("whsec_")

    @patch("common.url_safety._dns_lookup", return_value=["10.0.0.5"])
    def test_private_webhook_url_rejected(self, _dns):
        user = _pro_user()
        response = _session(user).post(
            reverse("api-key-list"), {"name": "hook", "webhook_url": "https://internal.example/hook"}, format="json"
        )
        assert response.status_code == 400
        assert "webhook_url" in response.data

    def test_plain_http_webhook_rejected(self):
        user = _pro_user()
        response = _session(user).post(
            reverse("api-key-list"), {"name": "hook", "webhook_url": "http://example.com/hook"}, format="json"
        )
        assert response.status_code == 400

    def test_delete_revokes_instead_of_deleting(self):
        user = _pro_user()
        key, _ = ApiKey.issue(user, "x")
        response = _session(user).delete(reverse("api-key-detail", kwargs={"id": key.id}))
        assert response.status_code == 204
        key.refresh_from_db()
        assert key.revoked_at is not None

    def test_cannot_touch_someone_elses_key(self):
        key, _ = ApiKey.issue(_pro_user(), "x")
        response = _session(_pro_user()).delete(reverse("api-key-detail", kwargs={"id": key.id}))
        assert response.status_code == 404

    def test_api_key_cannot_manage_keys(self):
        user = _pro_user()
        _, raw = ApiKey.issue(user, "x")
        response = APIClient().get(reverse("api-key-list"), HTTP_AUTHORIZATION=f"Api-Key {raw}")
        assert response.status_code == 403


@pytest.mark.django_db
class TestApiKeyAuthentication:
    def test_authorization_header_works(self):
        user = _pro_user()
        _, raw = ApiKey.issue(user, "x")
        response = APIClient().get(reverse("me"), HTTP_AUTHORIZATION=f"Api-Key {raw}")
        assert response.status_code == 200
        assert response.data["email"] == user.email

    def test_x_api_key_header_works(self):
        user = _pro_user()
        _, raw = ApiKey.issue(user, "x")
        response = APIClient().get(reverse("me"), HTTP_X_API_KEY=raw)
        assert response.status_code == 200

    def test_revoked_key_is_rejected(self):
        user = _pro_user()
        key, raw = ApiKey.issue(user, "x")
        key.revoked_at = key.created_at
        key.save(update_fields=["revoked_at"])
        response = APIClient().get(reverse("me"), HTTP_AUTHORIZATION=f"Api-Key {raw}")
        assert response.status_code == 401

    def test_unknown_key_is_rejected(self):
        response = APIClient().get(reverse("me"), HTTP_AUTHORIZATION="Api-Key pl_nope")
        assert response.status_code == 401

    def test_downgraded_user_loses_api(self):
        user = _pro_user()
        _, raw = ApiKey.issue(user, "x")
        sub = get_or_create_subscription(user)
        sub.tier = Subscription.Tier.FREE
        sub.save(update_fields=["tier"])
        response = APIClient().get(reverse("me"), HTTP_AUTHORIZATION=f"Api-Key {raw}")
        assert response.status_code == 401

    def test_last_used_is_recorded(self):
        user = _pro_user()
        key, raw = ApiKey.issue(user, "x")
        APIClient().get(reverse("me"), HTTP_AUTHORIZATION=f"Api-Key {raw}")
        key.refresh_from_db()
        assert key.last_used_at is not None

    @patch("content.views.process_submission.delay")
    def test_upload_via_key_links_submission(self, _delay, sample_jpeg):
        user = _pro_user()
        key, raw = ApiKey.issue(user, "x")
        response = APIClient().post(
            reverse("submission-list"), {"file": sample_jpeg}, format="multipart", HTTP_AUTHORIZATION=f"Api-Key {raw}"
        )
        assert response.status_code == 201
        assert Submission.objects.get(id=response.data["id"]).api_key_id == key.id


class TestWebhookSigning:
    def test_signature_is_hmac_over_timestamp_and_body(self):
        body, headers = encode({"event": "submission.completed", "x": 1}, "whsec_abc", now=1700000000)
        expected = "sha256=" + hmac.new(b"whsec_abc", b"1700000000." + body, hashlib.sha256).hexdigest()
        assert headers[SIGNATURE_HEADER] == expected
        assert headers[TIMESTAMP_HEADER] == "1700000000"
        assert sign("whsec_abc", "1700000000", body) == expected

    def test_body_is_canonical_json(self):
        body, _ = encode({"event": "e", "b": 2, "a": 1}, "s", now=1)
        assert body == b'{"a":1,"b":2,"event":"e"}'


@pytest.mark.django_db
class TestWebhookDelivery:
    def _completed_with_key(self, webhook_url="https://example.com/hook"):
        user = _pro_user()
        key, _ = ApiKey.issue(user, "x", webhook_url)
        sub = SubmissionFactory(
            user=user, api_key=key, status=Submission.Status.COMPLETED,
            final_verdict="fake", final_score=0.91, tribunal_version="1.2",
        )
        return sub, key

    @patch("users.tasks.safe_post")
    def test_posts_signed_payload(self, mock_post):
        sub, key = self._completed_with_key()
        mock_post.return_value = MagicMock(status_code=200)
        assert deliver_submission_webhook(str(sub.id)) == "200"
        _, kwargs = mock_post.call_args
        payload = json.loads(kwargs["data"])
        assert payload["submission_id"] == str(sub.id)
        assert payload["verdict"] == "fake"
        headers = kwargs["headers"]
        assert headers[SIGNATURE_HEADER] == sign(key.webhook_secret, headers[TIMESTAMP_HEADER], kwargs["data"])
        key.refresh_from_db()
        assert key.last_webhook_status == "200"

    @patch("users.tasks.safe_post", side_effect=UnsafeUrlError("URL not allowed"))
    def test_blocked_url_is_recorded_not_retried(self, _post):
        sub, key = self._completed_with_key()
        assert deliver_submission_webhook(str(sub.id)) == "blocked_url"
        key.refresh_from_db()
        assert key.last_webhook_status == "blocked_url"

    @patch("users.tasks.safe_post")
    def test_revoked_key_skips(self, mock_post):
        sub, key = self._completed_with_key()
        key.revoked_at = key.created_at
        key.save(update_fields=["revoked_at"])
        assert deliver_submission_webhook(str(sub.id)) == "skipped"
        mock_post.assert_not_called()

    @patch("users.tasks.safe_post")
    def test_no_webhook_url_skips(self, mock_post):
        sub, _ = self._completed_with_key(webhook_url="")
        assert deliver_submission_webhook(str(sub.id)) == "skipped"
        mock_post.assert_not_called()

    def test_payload_shape(self):
        sub, _ = self._completed_with_key()
        payload = build_payload(sub)
        assert set(payload) >= {"event", "submission_id", "verdict", "score", "tribunal_version"}


@pytest.mark.django_db
class TestWebhookTrigger:
    @patch("analyzers.tasks.deliver_submission_webhook.delay")
    def test_aggregation_enqueues_webhook_for_api_submissions(self, mock_delay):
        user = _pro_user()
        key, _ = ApiKey.issue(user, "x", "")
        sub = SubmissionFactory(user=user, api_key=key, status=Submission.Status.PROCESSING)
        AnalysisResultFactory(submission=sub, analyzer=AnalyzerConfigFactory(name="hook_member"), evidence={"ai_probability": 0.1})
        aggregate_verdicts([], str(sub.id))
        mock_delay.assert_called_once_with(str(sub.id))

    @patch("analyzers.tasks.deliver_submission_webhook.delay")
    def test_browser_submissions_do_not_enqueue(self, mock_delay):
        sub = SubmissionFactory(status=Submission.Status.PROCESSING)
        AnalysisResultFactory(submission=sub, analyzer=AnalyzerConfigFactory(name="hook_member2"), evidence={"ai_probability": 0.1})
        aggregate_verdicts([], str(sub.id))
        mock_delay.assert_not_called()
