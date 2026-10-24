from rest_framework import serializers

from common.names import display_name

from .access import can_supervise
from .attention import FLAGGED, TEXT_FLAGS, is_cleared
from .models import Classroom, Membership, OrgMember, ShadowSet
from .shadow import MAX_TARGET

FLAG_ORDER = [
    "ai_text", "ai_trace", "trace_hidden", "ai_image", "ai_media", "hidden_text",
    "tricks", "shadow", "copy", "sources", "age", "style",
]
NOTES = {
    "text too short for a verdict": "too_short",
    "language not calibrated": "language",
}


def submission_note(obj) -> str | None:
    for result in obj.analysis_results.all():
        if result.analyzer.name == "text_classifier":
            evidence = result.evidence if isinstance(result.evidence, dict) else {}
            return NOTES.get(evidence.get("reason"))
    return None


def submission_flags(obj) -> list[str]:
    if is_cleared(obj):
        return []
    flags = []
    is_image = obj.mime_type.startswith("image/")
    is_media = obj.mime_type.startswith(("audio/", "video/"))
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
    if is_media and obj.final_verdict in FLAGGED:
        flags.append("ai_media")
    return sorted(set(flags), key=FLAG_ORDER.index)


def latest_objection(obj):
    objections = sorted(obj.objections.all(), key=lambda o: o.created_at, reverse=True)
    return objections[0] if objections else None


def supervisor_ids(classroom) -> set[int]:
    ids = {classroom.owner_id}
    if classroom.organization_id:
        ids |= set(
            OrgMember.objects.filter(organization_id=classroom.organization_id, role=OrgMember.Role.ADMIN)
            .values_list("user_id", flat=True)
        )
    return ids


def is_unattributed(submission, context: dict) -> bool:
    members = context.get("members")
    supervisors = context.get("supervisors")
    if members is None or supervisors is None:
        return False
    return submission.user_id not in members and submission.user_id in supervisors


def class_context(classroom) -> dict:
    return {
        "members": set(Membership.objects.filter(classroom=classroom).values_list("user_id", flat=True)),
        "supervisors": supervisor_ids(classroom),
    }


class ClassroomSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    join_code = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    student_count = serializers.IntegerField(read_only=True, default=0)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True, default=None)
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)
    attention = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = (
            "id", "name", "level", "role", "join_code", "owner_name", "student_count", "archived", "created_at",
            "organization_slug", "organization_name", "attention",
        )
        read_only_fields = (
            "id", "role", "join_code", "owner_name", "student_count", "created_at",
            "organization_slug", "organization_name", "attention",
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

    def get_owner_name(self, obj):
        return display_name(obj.owner)

    def get_attention(self, obj):
        if not self._is_owner(obj):
            return None
        return self.context.get("attention", {}).get(obj.pk)


class MemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email")
    total = serializers.IntegerField(default=0)
    flagged = serializers.IntegerField(default=0)
    last_submission_at = serializers.DateTimeField(allow_null=True, default=None)

    class Meta:
        model = Membership
        fields = ("user_id", "username", "name", "email", "joined_at", "total", "flagged", "last_submission_at")

    def get_name(self, obj):
        return display_name(obj.user)


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
    student = serializers.SerializerMethodField()
    uploaded_by = serializers.SerializerMethodField()
    unattributed = serializers.SerializerMethodField()
    words = serializers.SerializerMethodField()
    originality = serializers.SerializerMethodField()
    flags = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    objection = serializers.SerializerMethodField()
    cleared = serializers.SerializerMethodField()

    def get_student(self, obj):
        return display_name(obj.user)

    def get_uploaded_by(self, obj):
        return display_name(obj.uploaded_by) if obj.uploaded_by_id else None

    def get_unattributed(self, obj):
        return is_unattributed(obj, self.context)

    def get_flags(self, obj):
        return submission_flags(obj) if obj.status == "completed" else []

    def get_note(self, obj):
        return submission_note(obj) if obj.status == "completed" else None

    def get_originality(self, obj):
        report = getattr(obj, "plagiarism_report", None)
        return report.originality if report is not None and report.status == "done" else None

    def get_words(self, obj):
        return ((obj.metadata or {}).get("document") or {}).get("words")

    def get_objection(self, obj):
        objection = latest_objection(obj)
        if objection is None:
            return None
        return {
            "status": objection.status,
            "decision": objection.decision,
            "overdue": objection.overdue,
            "due_at": objection.due_at,
            "responded_at": objection.responded_at,
        }

    def get_cleared(self, obj):
        return is_cleared(obj)


class ShadowSetSerializer(serializers.ModelSerializer):
    answers = serializers.IntegerField(source="answer_count", read_only=True, default=0)
    target = serializers.IntegerField(min_value=1, max_value=MAX_TARGET, default=8)
    prompt = serializers.CharField(min_length=15, max_length=2000)

    class Meta:
        model = ShadowSet
        fields = ("id", "prompt", "language", "target", "status", "error", "answers", "created_at")
        read_only_fields = ("id", "language", "status", "error", "answers", "created_at")
