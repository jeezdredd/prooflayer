from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing.permissions import CanUseApi
from common.demo import DemoLockedWritesMixin
from common.url_safety import UnsafeUrlError, validate_public_url

from .models import ApiKey

MAX_ACTIVE_KEYS = 10


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = (
            "id", "name", "prefix", "webhook_url", "created_at", "last_used_at",
            "revoked_at", "last_webhook_at", "last_webhook_status",
        )
        read_only_fields = ("id", "prefix", "created_at", "last_used_at", "revoked_at", "last_webhook_at", "last_webhook_status")

    def validate_webhook_url(self, value):
        if not value:
            return ""
        if not value.startswith("https://"):
            raise serializers.ValidationError("Webhook URL must use https.")
        try:
            validate_public_url(value)
        except UnsafeUrlError as exc:
            raise serializers.ValidationError("Webhook URL must resolve to a public address.") from exc
        return value


class SessionOnlyMixin:
    """Keys are managed from a logged-in browser session; an API key cannot mint or revoke keys."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if isinstance(request.auth, ApiKey):
            raise PermissionDenied("API keys cannot manage API keys.")


class ApiKeyListCreateView(DemoLockedWritesMixin, SessionOnlyMixin, generics.ListCreateAPIView):
    serializer_class = ApiKeySerializer
    permission_classes = [IsAuthenticated, CanUseApi]
    pagination_class = None

    def get_queryset(self):
        return ApiKey.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if ApiKey.objects.filter(user=request.user, revoked_at__isnull=True).count() >= MAX_ACTIVE_KEYS:
            return Response({"detail": f"At most {MAX_ACTIVE_KEYS} active keys."}, status=status.HTTP_400_BAD_REQUEST)
        key, raw = ApiKey.issue(
            request.user,
            serializer.validated_data["name"],
            serializer.validated_data.get("webhook_url", ""),
        )
        data = ApiKeySerializer(key).data
        data["key"] = raw
        data["webhook_secret"] = key.webhook_secret
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyDetailView(DemoLockedWritesMixin, SessionOnlyMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ApiKeySerializer
    permission_classes = [IsAuthenticated, CanUseApi]
    lookup_field = "id"

    def get_queryset(self):
        return ApiKey.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        key = serializer.save()
        if key.webhook_url and not key.webhook_secret:
            key.webhook_secret = ApiKey.new_webhook_secret()
            key.save(update_fields=["webhook_secret"])

    def perform_destroy(self, instance):
        if instance.revoked_at is None:
            instance.revoked_at = timezone.now()
            instance.save(update_fields=["revoked_at"])
