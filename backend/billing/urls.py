from django.urls import path

from .views import (
    CreateCheckoutView,
    CustomerPortalView,
    SubscriptionView,
    paddle_webhook,
)

urlpatterns = [
    path("subscription/", SubscriptionView.as_view(), name="subscription"),
    path("checkout/", CreateCheckoutView.as_view(), name="create-checkout"),
    path("portal/", CustomerPortalView.as_view(), name="customer-portal"),
    path("webhook/", paddle_webhook, name="paddle-webhook"),
]
