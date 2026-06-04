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

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            "completed": ("bg-green-100 text-green-800", "completed"),
            "failed": ("bg-red-100 text-red-800", "failed"),
            "processing": ("bg-yellow-100 text-yellow-800", "processing"),
            "pending": ("bg-gray-100 text-gray-600", "pending"),
        }
        cls, label = colors.get(obj.status, ("bg-gray-100 text-gray-600", obj.status))
        return format_html(
            '<span class="px-2 py-0.5 rounded text-xs font-medium {}">{}</span>',
            cls, label,
        )

    @admin.display(description="Verdict", ordering="final_verdict")
    def verdict_badge(self, obj):
        if not obj.final_verdict:
            return format_html('<span class="text-gray-400 text-xs">-</span>')
        colors = {
            "authentic": ("bg-green-100 text-green-800", "AUTHENTIC"),
            "likely_authentic": ("bg-green-50 text-green-700", "LIKELY AUTHENTIC"),
            "suspicious": ("bg-yellow-100 text-yellow-800", "SUSPICIOUS"),
            "likely_fake": ("bg-orange-100 text-orange-800", "LIKELY FAKE"),
            "fake": ("bg-red-100 text-red-800", "FAKE"),
            "inconclusive": ("bg-gray-100 text-gray-600", "INCONCLUSIVE"),
        }
        cls, label = colors.get(obj.final_verdict, ("bg-gray-100 text-gray-600", obj.final_verdict.upper()))
        score = f" {obj.final_score:.0%}" if obj.final_score is not None else ""
        return format_html(
            '<span class="px-2 py-0.5 rounded text-xs font-medium {}">{}{}</span>',
            cls, label, score,
        )

    @admin.display(description="Training label", ordering="verified_label")
    def training_badge(self, obj):
        if not obj.approved_for_training:
            return format_html('<span class="text-gray-400 text-xs">not approved</span>')
        label = obj.verified_label or "approved"
        cls = "bg-green-100 text-green-800" if label == "real" else "bg-red-100 text-red-800"
        return format_html(
            '<span class="px-2 py-0.5 rounded text-xs font-medium {}">{}</span>',
            cls, label.upper(),
        )


@admin.register(KnownFakeHash)
class KnownFakeHashAdmin(ModelAdmin):
    list_display = ("sha256_hash", "source", "added_at")
    search_fields = ("sha256_hash", "source")
