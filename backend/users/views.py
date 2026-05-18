from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailVerificationToken
from .serializers import RegisterSerializer, UserSerializer
from .tasks import send_verification_email

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email.delay(user.id)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


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
    def post(self, request):
        user = request.user
        if user.is_verified:
            return Response({"detail": "already verified"}, status=status.HTTP_400_BAD_REQUEST)
        send_verification_email.delay(user.id)
        return Response({"detail": "queued"})
