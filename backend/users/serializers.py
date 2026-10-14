from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from analyzers.training import forget
from classroom.access import is_student_only
from content.sensitivity import unpublish_all

User = get_user_model()

ACCEPT_TERMS_MESSAGE = "Accept the Terms of Service and Privacy Notice to continue."
TERMS_VERSION_MESSAGE = "These terms are out of date. Reload the page and accept the current version."


def age_fields(user, is_adult: bool) -> dict:
    if not is_adult:
        return {"is_adult": False, "age_confirmed_at": getattr(user, "age_confirmed_at", None)}
    if user is not None and user.is_adult and user.age_confirmed_at:
        return {"is_adult": True, "age_confirmed_at": user.age_confirmed_at}
    return {"is_adult": True, "age_confirmed_at": timezone.now()}


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    accept_terms = serializers.BooleanField(write_only=True, error_messages={"required": ACCEPT_TERMS_MESSAGE})
    is_adult = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = User
        fields = ("id", "email", "username", "password", "password_confirm", "allow_training", "accept_terms", "is_adult")
        read_only_fields = ("id",)

    def validate_accept_terms(self, value):
        if value is not True:
            raise serializers.ValidationError(ACCEPT_TERMS_MESSAGE)
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        validated_data.pop("accept_terms")
        now = timezone.now()
        if validated_data.get("allow_training"):
            validated_data["training_consent_at"] = now
        validated_data.update(age_fields(None, validated_data.pop("is_adult", False)))
        validated_data["terms_version"] = settings.TERMS_VERSION
        validated_data["terms_accepted_at"] = now
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    needs_terms = serializers.SerializerMethodField()
    student_only = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "email", "username", "avatar", "bio", "is_verified", "is_staff", "date_joined",
            "allow_training", "training_consent_at", "is_adult", "terms_version", "needs_terms", "student_only",
        )
        read_only_fields = (
            "id", "email", "is_verified", "is_staff", "date_joined", "training_consent_at", "terms_version",
        )

    def get_needs_terms(self, obj) -> bool:
        return obj.terms_version != settings.TERMS_VERSION

    def get_student_only(self, obj) -> bool:
        return is_student_only(obj)

    def update(self, instance, validated_data):
        if "is_adult" in validated_data:
            validated_data.update(age_fields(instance, validated_data["is_adult"]))
            if not validated_data["is_adult"]:
                unpublish_all(instance)
        if "allow_training" in validated_data and validated_data["allow_training"] != instance.allow_training:
            if validated_data["allow_training"]:
                validated_data["training_consent_at"] = timezone.now()
            else:
                validated_data["training_consent_at"] = None
                forget(instance.id)
        return super().update(instance, validated_data)


class AcceptTermsSerializer(serializers.Serializer):
    version = serializers.CharField()
    is_adult = serializers.BooleanField(required=False)

    def validate_version(self, value):
        if value != settings.TERMS_VERSION:
            raise serializers.ValidationError(TERMS_VERSION_MESSAGE)
        return value
