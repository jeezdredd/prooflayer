from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from analyzers.training import forget

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "username", "password", "password_confirm", "allow_training")
        read_only_fields = ("id",)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        if validated_data.get("allow_training"):
            validated_data["training_consent_at"] = timezone.now()
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", "email", "username", "avatar", "bio", "is_verified", "is_staff", "date_joined",
            "allow_training", "training_consent_at",
        )
        read_only_fields = ("id", "email", "is_verified", "is_staff", "date_joined", "training_consent_at")

    def update(self, instance, validated_data):
        if "allow_training" in validated_data and validated_data["allow_training"] != instance.allow_training:
            if validated_data["allow_training"]:
                validated_data["training_consent_at"] = timezone.now()
            else:
                validated_data["training_consent_at"] = None
                forget(instance.id)
        return super().update(instance, validated_data)
