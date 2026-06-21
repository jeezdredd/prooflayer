from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import EmailVerificationToken
from .serializers import RegisterSerializer, UserSerializer
from .tasks import send_verification_email

User = get_user_model()


class RegisterThrottle(AnonRateThrottle):
    scope = "register"
    rate = "5/hour"


class ResendVerificationThrottle(UserRateThrottle):
    scope = "resend_verification"
    rate = "5/hour"


class LoginThrottle(AnonRateThrottle):
    scope = "login"
    rate = "20/hour"


def _set_refresh_cookie(response, refresh: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
    )


def _clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (RegisterThrottle,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email.delay(user.id)
        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "delivery": "email" if settings.EMAIL_CONFIGURED else "console",
            },
            status=status.HTTP_201_CREATED,
        )
        _set_refresh_cookie(response, str(refresh))
        return response


class CookieTokenObtainPairView(TokenObtainPairView):
    throttle_classes = (LoginThrottle,)

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        refresh = response.data.pop("refresh", None)
        if refresh:
            _set_refresh_cookie(response, refresh)
        return response


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not refresh:
            return Response({"detail": "refresh cookie missing"}, status=status.HTTP_401_UNAUTHORIZED)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        data["refresh"] = refresh
        request._full_data = data
        response = super().post(request, *args, **kwargs)
        new_refresh = response.data.pop("refresh", None)
        if new_refresh:
            _set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        refresh = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except (TokenError, InvalidToken):
                pass
        response = Response({"detail": "logged out"})
        _clear_refresh_cookie(response)
        return response


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class VerifyEmailView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        token_str = (request.data.get("token") or "").strip()
        if not token_str:
            return Response({"detail": "token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = EmailVerificationToken.objects.select_related("user").get(token=token_str)
        except EmailVerificationToken.DoesNotExist:
            return Response({"detail": "invalid token"}, status=status.HTTP_404_NOT_FOUND)
        if not token.is_valid():
            return Response({"detail": "token expired or already used"}, status=status.HTTP_410_GONE)
        user = token.user
        if not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified"])
        token.mark_used()
        return Response({"detail": "verified", "email": user.email})


class ResendVerificationView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    throttle_classes = (ResendVerificationThrottle,)

    def post(self, request):
        user = request.user
        if user.is_verified:
            return Response({"detail": "already verified"}, status=status.HTTP_400_BAD_REQUEST)
        send_verification_email.delay(user.id)
        delivery = "email" if settings.EMAIL_CONFIGURED else "console"
        return Response({"detail": "queued", "delivery": delivery})
