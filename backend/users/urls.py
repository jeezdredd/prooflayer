from django.urls import path

from .api_keys import ApiKeyDetailView, ApiKeyListCreateView
from .views import (
    AcceptTermsView,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    EmailTestView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    ResendVerificationView,
    SessionView,
    UnsubscribeView,
    VerifyEmailView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CookieTokenObtainPairView.as_view(), name="login"),
    path("refresh/", CookieTokenRefreshView.as_view(), name="token-refresh"),
    path("session/", SessionView.as_view(), name="session"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("accept-terms/", AcceptTermsView.as_view(), name="accept-terms"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend-verification"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("unsubscribe/", UnsubscribeView.as_view(), name="unsubscribe"),
    path("email-test/", EmailTestView.as_view(), name="email-test"),
    path("api-keys/", ApiKeyListCreateView.as_view(), name="api-key-list"),
    path("api-keys/<int:id>/", ApiKeyDetailView.as_view(), name="api-key-detail"),
]
