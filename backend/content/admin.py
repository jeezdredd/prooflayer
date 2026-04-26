from django.contrib import admin

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
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "original_filename", "mime_type", "status",
        "final_verdict", "approved_for_training", "verified_label", "created_at",
    )
    list_filter = ("status", "mime_type", "is_known_fake", "approved_for_training", "verified_label")
    search_fields = ("original_filename", "sha256_hash")
    readonly_fields = ("id", "sha256_hash", "metadata")
    actions = [approve_as_real, approve_as_fake, revoke_training_approval]


@admin.register(KnownFakeHash)
class KnownFakeHashAdmin(admin.ModelAdmin):
    list_display = ("sha256_hash", "source", "added_at")
    search_fields = ("sha256_hash", "source")
