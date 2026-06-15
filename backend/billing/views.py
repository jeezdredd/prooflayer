import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscription, get_or_create_subscription, uploads_this_month
from .serializers import SubscriptionSerializer

logger = logging.getLogger(__name__)


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = get_or_create_subscription(request.user)
        used = uploads_this_month(request.user)
        data = SubscriptionSerializer(sub).data
        data["uploads_used"] = used
        data["uploads_limit"] = sub.uploads_per_month
        return Response(data)


class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            import stripe
        except ImportError:
            return Response({"detail": "Stripe not installed"}, status=500)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        price_id = settings.STRIPE_PRO_PRICE_ID
        if not price_id:
            return Response({"detail": "Stripe not configured"}, status=500)

        sub = get_or_create_subscription(request.user)

        if not sub.stripe_customer_id:
            customer = stripe.Customer.create(
                email=request.user.email,
                metadata={"user_id": str(request.user.id)},
            )
            sub.stripe_customer_id = customer.id
            sub.save(update_fields=["stripe_customer_id"])

        frontend_url = settings.FRONTEND_URL.rstrip("/")
        session = stripe.checkout.Session.create(
            customer=sub.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/pricing",
            metadata={"user_id": str(request.user.id)},
        )
        return Response({"url": session.url})


class CustomerPortalView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            import stripe
        except ImportError:
            return Response({"detail": "Stripe not installed"}, status=500)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        sub = get_or_create_subscription(request.user)
        if not sub.stripe_customer_id:
            return Response({"detail": "No billing account"}, status=400)

        frontend_url = settings.FRONTEND_URL.rstrip("/")
        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=f"{frontend_url}/pricing",
        )
        return Response({"url": session.url})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):
    try:
        import stripe
    except ImportError:
        return Response(status=500)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        return Response({"detail": "Invalid signature"}, status=400)
    except Exception as exc:
        logger.error("Stripe webhook error: %s", exc)
        return Response(status=400)

    _handle_event(event)
    return Response({"received": True})


def _handle_event(event):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    import datetime

    User = get_user_model()
    data = event["data"]["object"]

    if event["type"] in ("customer.subscription.created", "customer.subscription.updated"):
        customer_id = data.get("customer")
        stripe_sub_id = data.get("id")
        status_map = {
            "active": Subscription.Status.ACTIVE,
            "past_due": Subscription.Status.PAST_DUE,
            "canceled": Subscription.Status.CANCELLED,
            "trialing": Subscription.Status.TRIALING,
        }
        new_status = status_map.get(data.get("status", ""), Subscription.Status.ACTIVE)
        period_end = data.get("current_period_end")
        period_end_dt = datetime.datetime.fromtimestamp(period_end, tz=timezone.utc) if period_end else None

        try:
            sub = Subscription.objects.get(stripe_customer_id=customer_id)
            sub.stripe_subscription_id = stripe_sub_id
            sub.status = new_status
            sub.tier = Subscription.Tier.PRO
            sub.current_period_end = period_end_dt
            sub.save(update_fields=["stripe_subscription_id", "status", "tier", "current_period_end"])
        except Subscription.DoesNotExist:
            logger.warning("No subscription found for customer %s", customer_id)

    elif event["type"] == "customer.subscription.deleted":
        customer_id = data.get("customer")
        try:
            sub = Subscription.objects.get(stripe_customer_id=customer_id)
            sub.status = Subscription.Status.CANCELLED
            sub.tier = Subscription.Tier.FREE
            sub.stripe_subscription_id = ""
            sub.save(update_fields=["status", "tier", "stripe_subscription_id"])
        except Subscription.DoesNotExist:
            pass
