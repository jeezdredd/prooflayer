from django.contrib import admin

from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "user", "contact_email", "created_at", "message_preview")
    list_filter = ("category", "created_at")
    search_fields = ("message", "contact_email", "user__email")
    readonly_fields = ("id", "category", "message", "contact_email", "user", "created_at")
    ordering = ("-created_at",)

    def message_preview(self, obj):
        return obj.message[:80] + ("..." if len(obj.message) > 80 else "")
    message_preview.short_description = "Message"
