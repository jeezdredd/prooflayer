from django.urls import path

from .views import (
    CreateCheckoutSessionView,
    CustomerPortalView,
    SubscriptionView,
    stripe_webhook,
)

urlpatterns = [
    path("subscription/", SubscriptionView.as_view(), name="subscription"),
    path("checkout/", CreateCheckoutSessionView.as_view(), name="create-checkout"),
    path("portal/", CustomerPortalView.as_view(), name="customer-portal"),
    path("webhook/", stripe_webhook, name="stripe-webhook"),
]
