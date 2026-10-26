from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from analyzers.training import forget
from api.models import Feedback
from billing.models import Subscription
from classroom.models import Classroom, Organization
from common.demo import DEMO_CODE, DEMO_MESSAGE, is_demo_email, refuse_demo
from content.models import Submission
from content.sensitivity import unpublish_all

from .models import EmailChangeToken, EmailLog, EmailVerificationToken, ProductUpdate, email_change_expiry
from .serializers import AcceptTermsSerializer, RegisterSerializer, UserSerializer, age_fields
from . import mail
from .mail import user_from_unsubscribe_token
from .mail_samples import KINDS, sample_context
from .tasks import (
    send_email_change_confirm,
    send_email_change_notice,
    send_email_changed_notice,
    send_password_reset_email,
    send_verification_email,
)

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


class PasswordResetThrottle(AnonRateThrottle):
    scope = "password_reset"


class EmailChangeThrottle(UserRateThrottle):
    scope = "email_change"


class EmailChangeResendThrottle(UserRateThrottle):
    scope = "email_change_resend"


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
    throttle_classes = ()

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
        refuse_demo(user)
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


class PasswordResetRequestView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = (PasswordResetThrottle,)

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        if is_demo_email(email):
            return _demo_response()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user is not None:
            send_password_reset_email.delay(user.id)
        return Response({"detail": "If the address has an account, a reset link is on its way."})


def _user_from_uid(uid: str):
    try:
        pk = force_str(urlsafe_base64_decode(uid or ""))
    except (TypeError, ValueError):
        return None
    return User.objects.filter(pk=pk, is_active=True).first() if pk.isdigit() else None


class PasswordResetConfirmView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = (PasswordResetThrottle,)

    def post(self, request):
        user = _user_from_uid(request.data.get("uid", ""))
        token = request.data.get("token", "")
        if user is None or not default_token_generator.check_token(user, token):
            return Response({"detail": "This reset link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)
        if is_demo_email(user.email):
            return _demo_response()
        password = request.data.get("password", "")
        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        fields = ["password"]
        if not user.is_verified:
            user.is_verified = True
            fields.append("is_verified")
        user.save(update_fields=fields)
        EmailChangeToken.cancel_open(user)
        for outstanding in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=outstanding)
        return Response({"detail": "Password changed. Sign in with the new one."})


def _demo_response():
    return Response({"detail": DEMO_MESSAGE, "code": DEMO_CODE}, status=status.HTTP_403_FORBIDDEN)


def _error(code: str, detail: str, http_status: int):
    return Response({"detail": detail, "code": code}, status=http_status)


def _delivery() -> str:
    return "email" if settings.EMAIL_CONFIGURED else "console"


def _email_in_use(email: str, user) -> bool:
    return User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists()


def _lock_user(pk: int):
    return User.objects.select_for_update().filter(pk=pk).first()


EMAIL_TAKEN = "Another account already uses this email."
EMAIL_INVALID = "Enter a valid email address."
LINK_INVALID = "This link is not valid."


class EmailChangeView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)

    def get_throttles(self):
        if self.request.method == "POST":
            return [EmailChangeThrottle()]
        return super().get_throttles()

    def post(self, request):
        user = request.user
        refuse_demo(user)
        if not user.check_password(str(request.data.get("password") or "")):
            return _error("wrong_password", "Password is incorrect.", status.HTTP_403_FORBIDDEN)
        new_email = User.objects.normalize_email(str(request.data.get("new_email") or "").strip())
        try:
            validate_email(new_email)
        except DjangoValidationError:
            return _error("invalid_email", EMAIL_INVALID, status.HTTP_400_BAD_REQUEST)
        if len(new_email) > User._meta.get_field("email").max_length or is_demo_email(new_email):
            return _error("invalid_email", EMAIL_INVALID, status.HTTP_400_BAD_REQUEST)
        if new_email.lower() == (user.email or "").lower():
            return _error("same_email", "This is already your email.", status.HTTP_400_BAD_REQUEST)
        if _email_in_use(new_email, user):
            return _error("email_taken", EMAIL_TAKEN, status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            _lock_user(user.pk)
            EmailChangeToken.cancel_open(user)
            change = EmailChangeToken.objects.create(user=user, new_email=new_email)
        send_email_change_confirm.delay(change.id)
        send_email_change_notice.delay(change.id, user.email)
        return Response(
            {"detail": "Confirmation link sent.", "pending_email": new_email, "delivery": _delivery()},
            status=status.HTTP_202_ACCEPTED,
        )

    def delete(self, request):
        EmailChangeToken.cancel_open(request.user)
        return Response({"detail": "Email change cancelled.", "pending_email": None})


class EmailChangeResendView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)
    throttle_classes = (EmailChangeResendThrottle,)

    def post(self, request):
        refuse_demo(request.user)
        change = EmailChangeToken.pending_for(request.user)
        if change is None:
            return _error("no_pending", "There is no email change waiting for confirmation.", status.HTTP_404_NOT_FOUND)
        change.expires_at = email_change_expiry()
        change.save(update_fields=["expires_at"])
        send_email_change_confirm.delay(change.id)
        return Response({"detail": "Confirmation link sent.", "pending_email": change.new_email, "delivery": _delivery()})


class EmailChangeConfirmView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request):
        token_str = str(request.data.get("token") or "").strip()
        if not token_str:
            return _error("invalid", LINK_INVALID, status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                result = self._apply(token_str)
        except IntegrityError:
            return _error("email_taken", EMAIL_TAKEN, status.HTTP_409_CONFLICT)
        if isinstance(result, Response):
            return result
        user, old_email = result
        send_email_changed_notice.delay(user.id, old_email)
        return Response({"detail": "Email changed.", "email": user.email})

    def _apply(self, token_str: str):
        user_id = EmailChangeToken.objects.filter(token=token_str).values_list("user_id", flat=True).first()
        if user_id is None:
            return _error("invalid", LINK_INVALID, status.HTTP_404_NOT_FOUND)
        user = _lock_user(user_id)
        change = EmailChangeToken.objects.select_for_update().get(token=token_str)
        if user is None or not user.is_active:
            return _error("invalid", LINK_INVALID, status.HTTP_404_NOT_FOUND)
        if change.used_at is not None:
            return _error("used", "This link was already used.", status.HTTP_410_GONE)
        if change.cancelled_at is not None:
            return _error("cancelled", "This link no longer works: the change was cancelled or a newer link was sent.", status.HTTP_410_GONE)
        if change.is_expired:
            return _error("expired", "This link has expired.", status.HTTP_410_GONE)
        if is_demo_email(user.email):
            return _demo_response()
        if _email_in_use(change.new_email, user):
            return _error("email_taken", EMAIL_TAKEN, status.HTTP_409_CONFLICT)
        old_email = user.email
        now = timezone.now()
        change.used_at = now
        change.save(update_fields=["used_at"])
        EmailChangeToken.cancel_open(user)
        EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
        user.email = change.new_email
        user.is_verified = True
        user.save(update_fields=["email", "is_verified"])
        return user, old_email


class UnsubscribeView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request):
        token = request.query_params.get("token") or request.data.get("token") or ""
        user = user_from_unsubscribe_token(token)
        if user is None:
            return Response({"detail": "This unsubscribe link is invalid."}, status=status.HTTP_400_BAD_REQUEST)
        if user.email_updates:
            user.email_updates = False
            user.save(update_fields=["email_updates"])
        return Response({"detail": "unsubscribed", "email": user.email})


class EmailTestView(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request):
        logs = EmailLog.objects.order_by("-created_at")[:8]
        return Response({
            "configured": bool(getattr(settings, "EMAIL_CONFIGURED", False)),
            "kinds": list(KINDS),
            "to": request.user.email,
            "language": mail.lang_of(request.user),
            "recent": [
                {"at": log.created_at, "kind": log.kind, "to": log.to_email, "status": log.status, "error": log.error[:200]}
                for log in logs
            ],
        })

    def post(self, request):
        kind = request.data.get("kind", "")
        if kind not in KINDS:
            return Response({"kind": [f"Choose one of: {', '.join(KINDS)}."]}, status=status.HTTP_400_BAD_REQUEST)
        context = sample_context(kind, request.user, ProductUpdate.objects.order_by("-created_at").first())
        context["subject"] = f"[Test] {context['subject']}"
        try:
            result = mail.send(kind="test", to=[request.user.email], context=context, user=request.user)
        except Exception as exc:
            return Response({"status": "failed", "error": str(exc)[:300]}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"status": result, "to": request.user.email, "kind": kind})
