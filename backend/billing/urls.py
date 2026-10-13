from django.urls import path

from .views import (
    CreateCheckoutView,
    CustomerPortalView,
    PlanCatalogView,
    SubscriptionView,
    paddle_webhook,
)

urlpatterns = [
    path("plans/", PlanCatalogView.as_view(), name="plan-catalog"),
    path("subscription/", SubscriptionView.as_view(), name="subscription"),
    path("checkout/", CreateCheckoutView.as_view(), name="create-checkout"),
    path("portal/", CustomerPortalView.as_view(), name="customer-portal"),
    path("webhook/", paddle_webhook, name="paddle-webhook"),
]
