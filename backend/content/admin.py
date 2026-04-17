from django.contrib import admin

from .models import KnownFakeHash, Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "original_filename", "mime_type", "status", "final_verdict", "created_at")
    list_filter = ("status", "mime_type", "is_known_fake")
    search_fields = ("original_filename", "sha256_hash")
    readonly_fields = ("id", "sha256_hash", "metadata")


@admin.register(KnownFakeHash)
class KnownFakeHashAdmin(admin.ModelAdmin):
    list_display = ("sha256_hash", "source", "added_at")
    search_fields = ("sha256_hash", "source")
