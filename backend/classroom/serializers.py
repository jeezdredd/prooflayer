from rest_framework import serializers

from .access import can_supervise
from .models import Classroom, Membership, ShadowSet
from .shadow import MAX_TARGET

FLAGGED = {"fake", "likely_fake", "suspicious"}
FLAG_ORDER = ["ai_text", "ai_trace", "trace_hidden", "ai_image", "hidden_text", "tricks", "shadow", "copy", "sources", "age", "style"]
TEXT_FLAGS = {
    "text_classifier": "ai_text",
    "text_grade_fit": "age",
    "text_style": "style",
    "text_citations": "sources",
    "text_shadow": "shadow",
}


def submission_flags(obj) -> list[str]:
    flags = []
    is_image = obj.mime_type.startswith("image/")
    for result in obj.analysis_results.all():
        name = result.analyzer.name
        evidence = result.evidence if isinstance(result.evidence, dict) else {}
        if name == "text_evasion" and result.verdict in FLAGGED:
            flags.append("hidden_text" if evidence.get("hidden_characters") else "tricks")
        elif name in TEXT_FLAGS and result.verdict in FLAGGED:
            flags.append(TEXT_FLAGS[name])
        elif name == "metadata":
            if evidence.get("evasion"):
                flags.append("trace_hidden")
            elif evidence.get("ai_trace"):
                flags.append("ai_trace")
    report = getattr(obj, "plagiarism_report", None)
    if report is not None and report.status == "done" and report.originality is not None and report.originality < 85:
        flags.append("copy")
    if is_image and obj.final_verdict in FLAGGED and "ai_trace" not in flags and "trace_hidden" not in flags:
        flags.append("ai_image")
    return sorted(flags, key=FLAG_ORDER.index)


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
    uploaded_by = serializers.CharField(source="uploaded_by.username", default=None)
    words = serializers.SerializerMethodField()
    originality = serializers.SerializerMethodField()
    flags = serializers.SerializerMethodField()

    def get_flags(self, obj):
        return submission_flags(obj) if obj.status == "completed" else []

    def get_originality(self, obj):
        report = getattr(obj, "plagiarism_report", None)
        return report.originality if report is not None and report.status == "done" else None

    def get_words(self, obj):
        return ((obj.metadata or {}).get("document") or {}).get("words")


class ShadowSetSerializer(serializers.ModelSerializer):
    answers = serializers.IntegerField(source="answer_count", read_only=True, default=0)
    target = serializers.IntegerField(min_value=1, max_value=MAX_TARGET, default=8)
    prompt = serializers.CharField(min_length=15, max_length=2000)

    class Meta:
        model = ShadowSet
        fields = ("id", "prompt", "language", "target", "status", "error", "answers", "created_at")
        read_only_fields = ("id", "language", "status", "error", "answers", "created_at")
