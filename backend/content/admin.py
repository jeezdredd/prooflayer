from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display

from analyzers.training import snapshot

from .models import KnownFakeHash, Submission, VerdictObjection, VerdictOverride
from .reanalysis import can_reanalyze, restart_analysis


def _approve(queryset, label):
    eligible = queryset.filter(status="completed", classroom__isnull=True)
    eligible.update(approved_for_training=True, verified_label=label)
    for submission in eligible.select_related("user"):
        snapshot(submission)


def approve_as_real(modeladmin, request, queryset):
    _approve(queryset, "real")

approve_as_real.short_description = "Mark verified REAL (approve for training)"


def approve_as_fake(modeladmin, request, queryset):
    _approve(queryset, "fake")

approve_as_fake.short_description = "Mark verified AI (approve for training)"


def revoke_training_approval(modeladmin, request, queryset):
    queryset.update(approved_for_training=False, verified_label="")

revoke_training_approval.short_description = "Revoke training approval"


def mark_sensitive(modeladmin, request, queryset):
    queryset.update(is_sensitive=True)

mark_sensitive.short_description = "Mark as sensitive"


def unmark_sensitive(modeladmin, request, queryset):
    queryset.update(is_sensitive=False)

unmark_sensitive.short_description = "Unmark sensitive"


@admin.action(description="Re-analyze with current Tribunal", permissions=["change"])
def reanalyze(modeladmin: ModelAdmin, request: HttpRequest, queryset: QuerySet[Submission]) -> None:
    started = 0
    for submission in queryset:
        if can_reanalyze(submission):
            restart_analysis(submission)
            started += 1
    skipped = queryset.count() - started
    if started:
        modeladmin.message_user(request, f"Re-analysis started for {started} submission(s).", messages.SUCCESS)
    if skipped:
        modeladmin.message_user(
            request,
            f"Skipped {skipped}: still being analyzed or the file was deleted under the retention policy.",
            messages.WARNING,
        )


@admin.register(Submission)
class SubmissionAdmin(ModelAdmin):
    list_display = (
        "original_filename", "user", "classroom", "verdict_badge", "score",
        "status_badge", "training_badge", "created_at",
    )
    list_filter = (
        "status", "final_verdict", "mime_type", "tribunal_version", "is_known_fake", "is_public", "is_sensitive",
        "approved_for_training", "verified_label", "created_at",
    )
    search_fields = ("id", "original_filename", "sha256_hash", "user__email", "classroom__name")
    readonly_fields = (
        "id", "sha256_hash", "metadata", "tribunal_version", "tribunal_fingerprint", "created_at", "updated_at",
    )
    raw_id_fields = ("user", "classroom", "batch", "api_key")
    list_select_related = ("user", "classroom")
    date_hierarchy = "created_at"
    actions = [
        reanalyze, approve_as_real, approve_as_fake, revoke_training_approval, mark_sensitive, unmark_sensitive,
    ]
    list_per_page = 50

    _BADGE_STYLE = (
        "display:inline-block;padding:2px 8px;border-radius:4px;"
        "font-size:11px;font-weight:600;letter-spacing:.03em;white-space:nowrap;"
    )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            "completed": "#14532d;color:#86efac",
            "failed": "#7f1d1d;color:#fca5a5",
            "processing": "#78350f;color:#fcd34d",
            "pending": "#1f2937;color:#9ca3af",
        }
        style = colors.get(obj.status, "#1f2937;color:#9ca3af")
        return format_html(
            '<span style="{}background:{}">{}</span>',
            self._BADGE_STYLE, style, obj.status,
        )

    @admin.display(description="Verdict", ordering="final_verdict")
    def verdict_badge(self, obj):
        if not obj.final_verdict:
            return format_html('<span style="color:#6b7280;font-size:11px">-</span>')
        colors = {
            "authentic": "#14532d;color:#86efac",
            "likely_authentic": "#166534;color:#bbf7d0",
            "suspicious": "#78350f;color:#fcd34d",
            "likely_fake": "#7c2d12;color:#fdba74",
            "fake": "#7f1d1d;color:#fca5a5",
            "inconclusive": "#1f2937;color:#9ca3af",
            "needs_review": "#1e3a8a;color:#93c5fd",
        }
        style = colors.get(obj.final_verdict, "#1f2937;color:#9ca3af")
        labels = {
            "authentic": "AUTHENTIC",
            "likely_authentic": "LIKELY AUTH",
            "suspicious": "SUSPICIOUS",
            "likely_fake": "LIKELY FAKE",
            "fake": "FAKE",
            "inconclusive": "INCONCLUSIVE",
            "needs_review": "NEEDS REVIEW",
        }
        label = labels.get(obj.final_verdict, obj.final_verdict.upper())
        return format_html(
            '<span style="{}background:{}">{}</span>',
            self._BADGE_STYLE, style, label,
        )

    @admin.display(description="Score", ordering="final_score")
    def score(self, obj):
        return "-" if obj.final_score is None else f"{obj.final_score:.0%}"

    @admin.display(description="Training label", ordering="verified_label")
    def training_badge(self, obj):
        if not obj.approved_for_training:
            return format_html('<span style="color:#6b7280;font-size:11px">not approved</span>')
        label = obj.verified_label or "approved"
        style = "#14532d;color:#86efac" if label == "real" else "#7f1d1d;color:#fca5a5"
        return format_html(
            '<span style="{}background:{}">{}</span>',
            self._BADGE_STYLE, style, label.upper(),
        )


@admin.register(KnownFakeHash)
class KnownFakeHashAdmin(ModelAdmin):
    list_display = ("sha256_hash", "source", "added_at")
    search_fields = ("sha256_hash", "source")


@admin.register(VerdictObjection)
class VerdictObjectionAdmin(ModelAdmin):
    list_display = ("submission", "author", "status_badge", "decision", "due_state", "created_at", "responded_at")
    list_filter = ("status", "decision", "created_at")
    search_fields = ("reason", "response", "author__email", "submission__original_filename")
    list_select_related = ("submission", "author")
    raw_id_fields = ("submission", "author", "responded_by")
    readonly_fields = ("created_at",)
    ordering = ("status", "due_at")

    @display(description="Status", ordering="status", label={"open": "warning", "answered": "success"})
    def status_badge(self, obj: VerdictObjection) -> str:
        return obj.status

    @display(
        description="Due",
        ordering="due_at",
        label={"overdue": "danger", "on time": "info", "answered": "success"},
    )
    def due_state(self, obj: VerdictObjection) -> str:
        if obj.status != VerdictObjection.Status.OPEN:
            return "answered"
        return "overdue" if obj.due_at < timezone.now() else "on time"


@admin.register(VerdictOverride)
class VerdictOverrideAdmin(ModelAdmin):
    list_display = ("submission", "reviewer", "previous_verdict", "new_verdict", "created_at")
    list_filter = ("new_verdict", "created_at")
    search_fields = ("reason", "reviewer__email", "submission__original_filename")
    list_select_related = ("submission", "reviewer")
    readonly_fields = ("submission", "reviewer", "previous_verdict", "new_verdict", "reason", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
