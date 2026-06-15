import hashlib
import hmac
import json
import logging

import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscription, get_or_create_subscription, uploads_this_month
from .serializers import SubscriptionSerializer

logger = logging.getLogger(__name__)

PADDLE_API_BASE = "https://api.paddle.com"


def _paddle_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = get_or_create_subscription(request.user)
        used = uploads_this_month(request.user)
        data = SubscriptionSerializer(sub).data
        data["uploads_used"] = used
        data["uploads_limit"] = sub.uploads_per_month
        return Response(data)


class CreateCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        price_id = settings.PADDLE_PRO_PRICE_ID
        if not price_id or not settings.PADDLE_API_KEY:
            return Response({"detail": "Paddle not configured"}, status=500)

        frontend_url = settings.FRONTEND_URL.rstrip("/")
        sub = get_or_create_subscription(request.user)

        payload = {
            "items": [{"price_id": price_id, "quantity": 1}],
            "customer": {"email": request.user.email},
            "custom_data": {"user_id": str(request.user.id)},
            "checkout": {
                "url": f"{frontend_url}/pricing",
            },
        }

        if sub.paddle_customer_id:
            payload["customer"] = {"id": sub.paddle_customer_id}

        resp = requests.post(
            f"{PADDLE_API_BASE}/transactions",
            headers=_paddle_headers(),
            json=payload,
            timeout=15,
        )
        if not resp.ok:
            logger.error("Paddle checkout error: %s", resp.text)
            return Response({"detail": "Checkout failed"}, status=502)

        data = resp.json().get("data", {})
        checkout_url = data.get("checkout", {}).get("url", "")
        customer_id = data.get("customer_id", "")

        if customer_id and not sub.paddle_customer_id:
            sub.paddle_customer_id = customer_id
            sub.save(update_fields=["paddle_customer_id"])

        return Response({"url": checkout_url})


class CustomerPortalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub = get_or_create_subscription(request.user)
        if not sub.paddle_customer_id or not settings.PADDLE_API_KEY:
            return Response({"detail": "No billing account"}, status=400)

        resp = requests.post(
            f"{PADDLE_API_BASE}/customers/{sub.paddle_customer_id}/portal-sessions",
            headers=_paddle_headers(),
            json={},
            timeout=15,
        )
        if not resp.ok:
            logger.error("Paddle portal error: %s", resp.text)
            return Response({"detail": "Portal unavailable"}, status=502)

        urls = resp.json().get("data", {}).get("urls", {})
        portal_url = urls.get("general", {}).get("overview", "")
        return Response({"url": portal_url})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def paddle_webhook(request):
    secret = settings.PADDLE_WEBHOOK_SECRET
    signature_header = request.META.get("HTTP_PADDLE_SIGNATURE", "")
    payload = request.body

    if secret and not _verify_paddle_signature(payload, signature_header, secret):
        return Response({"detail": "Invalid signature"}, status=400)

    try:
        event = json.loads(payload)
    except Exception:
        return Response(status=400)

    _handle_event(event)
    return Response({"received": True})


def _verify_paddle_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(";"))
        ts = parts.get("ts", "")
        h1 = parts.get("h1", "")
        signed = f"{ts}:{payload.decode()}"
        expected = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, h1)
    except Exception:
        return False


def _handle_event(event: dict):
    event_type = event.get("event_type", "")
    data = event.get("data", {})

    if event_type in ("subscription.created", "subscription.updated"):
        customer_id = data.get("customer_id", "")
        sub_id = data.get("id", "")
        paddle_status = data.get("status", "active")
        period_end_str = data.get("current_billing_period", {}).get("ends_at")

        status_map = {
            "active": Subscription.Status.ACTIVE,
            "past_due": Subscription.Status.PAST_DUE,
            "canceled": Subscription.Status.CANCELLED,
            "trialing": Subscription.Status.TRIALING,
            "paused": Subscription.Status.PAST_DUE,
        }
        new_status = status_map.get(paddle_status, Subscription.Status.ACTIVE)

        period_end_dt = None
        if period_end_str:
            from django.utils.dateparse import parse_datetime
            period_end_dt = parse_datetime(period_end_str)

        custom_data = data.get("custom_data", {}) or {}
        user_id = custom_data.get("user_id")

        sub = None
        if customer_id:
            sub = Subscription.objects.filter(paddle_customer_id=customer_id).first()
        if sub is None and user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                sub = get_or_create_subscription(user)
            except User.DoesNotExist:
                pass

        if sub is None:
            logger.warning("paddle webhook: no subscription for customer=%s user_id=%s", customer_id, user_id)
            return

        sub.paddle_customer_id = customer_id
        sub.paddle_subscription_id = sub_id
        sub.status = new_status
        sub.tier = Subscription.Tier.PRO
        sub.current_period_end = period_end_dt
        sub.save(update_fields=["paddle_customer_id", "paddle_subscription_id", "status", "tier", "current_period_end"])

    elif event_type == "subscription.canceled":
        sub_id = data.get("id", "")
        customer_id = data.get("customer_id", "")
        sub = Subscription.objects.filter(paddle_subscription_id=sub_id).first()
        if sub is None and customer_id:
            sub = Subscription.objects.filter(paddle_customer_id=customer_id).first()
        if sub:
            sub.status = Subscription.Status.CANCELLED
            sub.tier = Subscription.Tier.FREE
            sub.paddle_subscription_id = ""
            sub.save(update_fields=["status", "tier", "paddle_subscription_id"])
