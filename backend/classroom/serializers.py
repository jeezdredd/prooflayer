from rest_framework import serializers

from .access import can_supervise
from .models import Classroom, Membership


class ClassroomSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    join_code = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source="owner.username", read_only=True)
    student_count = serializers.IntegerField(read_only=True, default=0)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True, default=None)
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)

    class Meta:
        model = Classroom
        fields = (
            "id", "name", "level", "role", "join_code", "owner_name", "student_count", "archived", "created_at",
            "organization_slug", "organization_name",
        )
        read_only_fields = (
            "id", "role", "join_code", "owner_name", "student_count", "created_at",
            "organization_slug", "organization_name",
        )

    def _is_owner(self, obj) -> bool:
        request = self.context.get("request")
        if not request:
            return False
        cache = self.context.setdefault("_supervises", {})
        if obj.pk not in cache:
            cache[obj.pk] = can_supervise(obj, request.user)
        return cache[obj.pk]

    def get_role(self, obj):
        return "teacher" if self._is_owner(obj) else "student"

    def get_join_code(self, obj):
        return obj.join_code if self._is_owner(obj) else None


class MemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")
    email = serializers.EmailField(source="user.email")
    total = serializers.IntegerField(default=0)
    flagged = serializers.IntegerField(default=0)
    last_submission_at = serializers.DateTimeField(allow_null=True, default=None)

    class Meta:
        model = Membership
        fields = ("user_id", "username", "email", "joined_at", "total", "flagged", "last_submission_at")


class ClassSubmissionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    original_filename = serializers.CharField()
    mime_type = serializers.CharField()
    status = serializers.CharField()
    final_verdict = serializers.CharField()
    final_score = serializers.FloatField(allow_null=True)
    tribunal_version = serializers.CharField()
    created_at = serializers.DateTimeField()
    student_id = serializers.IntegerField(source="user_id")
    student = serializers.CharField(source="user.username")
    words = serializers.SerializerMethodField()
    originality = serializers.SerializerMethodField()

    def get_originality(self, obj):
        report = getattr(obj, "plagiarism_report", None)
        return report.originality if report is not None and report.status == "done" else None

    def get_words(self, obj):
        return ((obj.metadata or {}).get("document") or {}).get("words")
