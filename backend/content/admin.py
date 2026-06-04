from django.contrib import admin
from django.utils.html import format_html

from unfold.admin import ModelAdmin

from .models import KnownFakeHash, Submission


def approve_as_real(modeladmin, request, queryset):
    queryset.filter(status="completed").update(approved_for_training=True, verified_label="real")

approve_as_real.short_description = "Approve selected as REAL (for training)"


def approve_as_fake(modeladmin, request, queryset):
    queryset.filter(status="completed").update(approved_for_training=True, verified_label="fake")

approve_as_fake.short_description = "Approve selected as FAKE (for training)"


def revoke_training_approval(modeladmin, request, queryset):
    queryset.update(approved_for_training=False, verified_label="")

revoke_training_approval.short_description = "Revoke training approval"


@admin.register(Submission)
class SubmissionAdmin(ModelAdmin):
    list_display = (
        "id", "user", "original_filename", "mime_type", "status_badge",
        "verdict_badge", "training_badge", "created_at",
    )
    list_filter = ("status", "mime_type", "is_known_fake", "approved_for_training", "verified_label")
    search_fields = ("original_filename", "sha256_hash")
    readonly_fields = ("id", "sha256_hash", "metadata")
    actions = [approve_as_real, approve_as_fake, revoke_training_approval]
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
        }
        style = colors.get(obj.final_verdict, "#1f2937;color:#9ca3af")
        labels = {
            "authentic": "AUTHENTIC",
            "likely_authentic": "LIKELY AUTH",
            "suspicious": "SUSPICIOUS",
            "likely_fake": "LIKELY FAKE",
            "fake": "FAKE",
            "inconclusive": "INCONCLUSIVE",
        }
        label = labels.get(obj.final_verdict, obj.final_verdict.upper())
        score = f" {obj.final_score:.0%}" if obj.final_score is not None else ""
        return format_html(
            '<span style="{}background:{}">{}{}</span>',
            self._BADGE_STYLE, style, label, score,
        )

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
