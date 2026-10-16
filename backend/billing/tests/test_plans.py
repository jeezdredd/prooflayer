import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from billing.models import Subscription, get_or_create_subscription
from billing.plans import PLANS
from classroom.models import Organization, OrgMember
from common.throttling import ApiKeyRateThrottle
from users.models import ApiKey
from users.tests.factories import UserFactory

PRICES = {
    "pro:month": "pri_pro_m", "pro:year": "pri_pro_y",
    "education:month": "pri_school_m", "education:year": "pri_school_y",
    "university:month": "pri_uni_m", "university:year": "",
    "enterprise:month": "pri_ent_m", "enterprise:year": "pri_ent_y",
}


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _on_plan(tier):
    user = UserFactory(is_verified=True)
    sub = get_or_create_subscription(user)
    sub.tier = tier
    sub.save(update_fields=["tier"])
    return user


class TestCatalogShape:
    def test_school_below_university(self):
        assert PLANS["pro"].monthly_usd < PLANS["education"].monthly_usd < PLANS["university"].monthly_usd
        assert PLANS["education"].uploads_per_month < PLANS["university"].uploads_per_month < PLANS["enterprise"].uploads_per_month

    def test_enterprise_is_sales_led(self):
        enterprise = PLANS["enterprise"]
        assert enterprise.monthly_usd is None and enterprise.yearly_usd is None
        assert not enterprise.self_serve

    def test_prices_end_in_99_and_yearly_saves_about_a_sixth(self):
        for plan in PLANS.values():
            if not plan.monthly_usd:
                continue
            assert round(plan.monthly_usd * 100) % 100 == 99
            assert round(plan.yearly_usd * 100) % 1200 == 1188
            assert 0.16 <= 1 - plan.yearly_usd / (plan.monthly_usd * 12) <= 0.18

    def test_only_education_plans_get_classroom(self):
        assert {k for k, p in PLANS.items() if p.classroom} == {"education", "university"}


@pytest.mark.django_db
class TestCatalogEndpoint:
    def test_public_catalog_with_checkout_availability(self, settings):
        settings.PADDLE_PRICE_IDS = PRICES
        response = _client().get(reverse("plan-catalog"))
        assert response.status_code == 200
        plans = {p["key"]: p for p in response.data["plans"]}
        assert list(plans) == ["free", "pro", "education", "university", "enterprise"]
        assert plans["university"]["checkout"] == {"month": True, "year": False}
        assert plans["free"]["checkout"] == {"month": False, "year": False}
        assert plans["education"]["name"] == "School"
        assert plans["enterprise"]["checkout"] == {"month": False, "year": False}
        assert plans["university"]["classroom"] is True


@pytest.mark.django_db
class TestSubscriptionFlags:
    def test_university_limits(self):
        sub = get_or_create_subscription(_on_plan(Subscription.Tier.UNIVERSITY))
        assert sub.uploads_per_month == 15000
        assert sub.can_classroom and sub.can_api and sub.can_compare

    def test_enterprise_has_no_classroom(self):
        sub = get_or_create_subscription(_on_plan(Subscription.Tier.ENTERPRISE))
        assert sub.uploads_per_month == 50000
        assert not sub.can_classroom

    def test_free_has_no_paid_features(self):
        sub = get_or_create_subscription(UserFactory())
        assert sub.uploads_per_month == 50
        assert not (sub.can_api or sub.can_compare or sub.can_download_pdf)


@pytest.mark.django_db
class TestCheckout:
    @pytest.fixture(autouse=True)
    def _paddle(self, settings):
        settings.PADDLE_PRICE_IDS = PRICES
        settings.PADDLE_API_KEY = "pdl_test"

    @patch("billing.views.requests.post")
    def test_checkout_uses_the_plan_and_interval_price(self, post):
        post.return_value = MagicMock(ok=True, json=lambda: {"data": {"id": "txn_1", "checkout": {"url": "https://pay.example/x"}, "customer_id": "ctm_1"}})
        user = UserFactory(is_verified=True)
        response = _client(user).post(reverse("create-checkout"), {"plan": "education", "interval": "year"}, format="json")
        assert response.status_code == 200
        assert response.data["url"] == "https://pay.example/x"
        assert response.data["transaction_id"] == "txn_1"
        assert post.call_args.args[0] == "https://api.paddle.com/transactions"
        sent = post.call_args.kwargs["json"]
        assert sent["items"] == [{"price_id": "pri_school_y", "quantity": 1}]
        assert sent["custom_data"]["plan"] == "education"

    def test_unpriced_interval_asks_to_contact_sales(self):
        response = _client(UserFactory()).post(reverse("create-checkout"), {"plan": "university", "interval": "year"}, format="json")
        assert response.status_code == 409
        assert response.data["code"] == "contact_sales"

    @pytest.mark.parametrize("body", [{"plan": "free"}, {"plan": "gold"}, {"plan": "pro", "interval": "week"}])
    def test_bad_plan_rejected(self, body):
        assert _client(UserFactory()).post(reverse("create-checkout"), body, format="json").status_code == 400

    def test_paying_user_is_sent_to_portal(self):
        user = _on_plan(Subscription.Tier.PRO)
        Subscription.objects.filter(user=user).update(paddle_subscription_id="sub_1")
        response = _client(user).post(reverse("create-checkout"), {"plan": "university"}, format="json")
        assert response.status_code == 409
        assert response.data["code"] == "manage_in_portal"


@pytest.mark.django_db
class TestWebhookTier:
    @pytest.fixture(autouse=True)
    def _paddle(self, settings):
        settings.PADDLE_PRICE_IDS = PRICES
        settings.PADDLE_WEBHOOK_SECRET = ""

    def _event(self, user, price):
        return {
            "event_type": "subscription.created",
            "data": {
                "id": "sub_9", "customer_id": "ctm_9", "status": "active",
                "items": [{"price": {"id": price}}],
                "custom_data": {"user_id": str(user.id)},
            },
        }

    def _send(self, event):
        return _client().post(reverse("paddle-webhook"), data=json.dumps(event), content_type="application/json")

    def test_price_decides_the_tier(self):
        user = UserFactory()
        assert self._send(self._event(user, "pri_uni_m")).status_code == 200
        assert Subscription.objects.get(user=user).tier == Subscription.Tier.UNIVERSITY

    def test_scheduled_cancel_is_recorded(self):
        user = UserFactory()
        event = self._event(user, "pri_uni_m")
        event["data"]["scheduled_change"] = {"action": "cancel", "effective_at": "2026-11-13T00:00:00Z"}
        self._send(event)
        sub = Subscription.objects.get(user=user)
        assert sub.cancel_scheduled and sub.is_active

    def test_unknown_price_keeps_the_tier(self):
        user = _on_plan(Subscription.Tier.PRO)
        self._send(self._event(user, "pri_mystery"))
        sub = Subscription.objects.get(user=user)
        assert sub.tier == Subscription.Tier.PRO
        assert sub.paddle_subscription_id == "sub_9"


@pytest.mark.django_db
class TestOrgLimits:
    def test_school_plan_gets_one_address(self):
        owner = _on_plan(Subscription.Tier.EDUCATION)
        Organization.create_for(owner, "First", "first-school")
        response = _client(owner).post(reverse("org-list"), {"name": "Second", "slug": "second-school"}, format="json")
        assert response.status_code == 402

    def test_university_gets_several_faculties(self):
        owner = _on_plan(Subscription.Tier.UNIVERSITY)
        Organization.create_for(owner, "Law", "law-faculty")
        response = _client(owner).post(reverse("org-list"), {"name": "Physics", "slug": "physics-faculty"}, format="json")
        assert response.status_code == 201

    @patch("classroom.org_views._owner_plan", return_value=replace(PLANS["education"], teacher_seats=2))
    def test_teacher_seats_are_enforced(self, _plan):
        owner = _on_plan(Subscription.Tier.EDUCATION)
        org = Organization.create_for(owner, "Lyceum", "lyceum-seats")
        url = reverse("org-join-teacher", kwargs={"slug": org.slug})
        first = UserFactory(is_verified=True)
        assert _client(first).post(url, {"code": org.teacher_code}, format="json").status_code == 201
        late = UserFactory(is_verified=True)
        assert _client(late).post(url, {"code": org.teacher_code}, format="json").status_code == 403
        assert _client(first).post(url, {"code": org.teacher_code}, format="json").status_code == 200
        assert OrgMember.objects.filter(organization=org).count() == 2


@pytest.mark.django_db
class TestApiRateByPlan:
    def test_enterprise_key_gets_its_plan_rate(self):
        cache.clear()
        key, _ = ApiKey.issue(_on_plan(Subscription.Tier.ENTERPRISE), "ci")
        throttle = ApiKeyRateThrottle()
        request = SimpleNamespace(auth=key, user=key.user, META={})
        assert throttle.allow_request(request, None)
        assert (throttle.num_requests, throttle.duration) == (600, 60)


@pytest.mark.django_db
def test_sandbox_checkout_goes_to_sandbox_api(settings):
    settings.PADDLE_PRICE_IDS = PRICES
    settings.PADDLE_API_KEY = "pdl_sdbx"
    settings.PADDLE_API_BASE = "https://sandbox-api.paddle.com"
    with patch("billing.views.requests.post") as post:
        post.return_value = MagicMock(ok=True, json=lambda: {"data": {"id": "txn_2", "checkout": {"url": ""}, "customer_id": ""}})
        _client(UserFactory()).post(reverse("create-checkout"), {"plan": "education", "interval": "year"}, format="json")
    assert post.call_args.args[0] == "https://sandbox-api.paddle.com/transactions"


@pytest.mark.django_db
def test_catalog_exposes_client_token_only_when_set(settings):
    settings.PADDLE_CLIENT_TOKEN = ""
    assert APIClient().get(reverse("plan-catalog")).data["paddle"] is None
    settings.PADDLE_CLIENT_TOKEN = "test_abc"
    settings.PADDLE_ENV = "sandbox"
    assert APIClient().get(reverse("plan-catalog")).data["paddle"] == {"environment": "sandbox", "client_token": "test_abc"}
