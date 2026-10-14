from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from analyzers.training import forget
from api.models import Feedback
from billing.models import Subscription
from classroom.models import Classroom, Organization
from content.models import Submission
from content.sensitivity import unpublish_all

from .models import EmailLog, EmailVerificationToken
from .serializers import AcceptTermsSerializer, RegisterSerializer, UserSerializer, age_fields
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



class SessionView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def get(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw:
            return Response({"user_id": None})
        try:
            token = RefreshToken(raw)
        except TokenError:
            return Response({"user_id": None})
        value = token.get(settings.SIMPLE_JWT.get("USER_ID_CLAIM", "user_id"))
        return Response({"user_id": int(value) if str(value).isdigit() else value})

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

    def delete(self, request):
        user = request.user
        if not user.check_password(request.data.get("password") or ""):
            return Response({"detail": "Password is incorrect."}, status=status.HTTP_403_FORBIDDEN)
        schools = list(Organization.objects.filter(owner=user).values_list("name", flat=True))
        if schools:
            return Response(
                {"detail": f"You own {', '.join(schools)}. Delete the school or ask support to hand it over first.", "code": "owns_organization"},
                status=status.HTTP_409_CONFLICT,
            )
        sub = Subscription.objects.filter(user=user).first()
        if sub and sub.paddle_subscription_id and sub.is_active and sub.tier != Subscription.Tier.FREE and not sub.cancel_scheduled:
            return Response(
                {"detail": "Cancel your paid subscription in the billing portal first, so you are not charged again.", "code": "active_subscription"},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            for classroom in Classroom.objects.filter(owner=user).select_related("organization"):
                if classroom.organization_id:
                    classroom.owner_id = classroom.organization.owner_id
                    classroom.save(update_fields=["owner"])
                else:
                    _delete_submissions(Submission.objects.filter(classroom=classroom))
                    classroom.delete()
            _delete_submissions(Submission.objects.filter(user=user))
            Feedback.objects.filter(user=user).delete()
            EmailLog.objects.filter(user=user).delete()
            if request.data.get("forget_training"):
                forget(user.id)
            user.delete()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


class AcceptTermsView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = AcceptTermsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        changes = {"terms_version": serializer.validated_data["version"], "terms_accepted_at": timezone.now()}
        if "is_adult" in request.data and "is_adult" in serializer.validated_data:
            changes.update(age_fields(user, serializer.validated_data["is_adult"]))
        for field, value in changes.items():
            setattr(user, field, value)
        user.save(update_fields=list(changes))
        if changes.get("is_adult") is False:
            unpublish_all(user)
        return Response(UserSerializer(user, context={"request": request}).data)


def _delete_submissions(queryset) -> None:
    for submission in queryset.only("file", "thumbnail").iterator(chunk_size=200):
        if submission.file:
            submission.file.delete(save=False)
        if submission.thumbnail:
            submission.thumbnail.delete(save=False)
    queryset.delete()


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
