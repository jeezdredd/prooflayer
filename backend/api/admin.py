from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ChangelogEntry, Feedback, RoadmapItem


@admin.register(Feedback)
class FeedbackAdmin(ModelAdmin):
    list_display = ("created_at", "category", "message_preview", "user", "contact_email")
    list_filter = ("category", "created_at")
    search_fields = ("message", "contact_email", "user__email")
    list_select_related = ("user",)
    readonly_fields = ("id", "category", "message", "contact_email", "user", "created_at")
    ordering = ("-created_at",)

    def message_preview(self, obj):
        return obj.message[:80] + ("..." if len(obj.message) > 80 else "")
    message_preview.short_description = "Message"


@admin.register(RoadmapItem)
class RoadmapItemAdmin(ModelAdmin):
    list_display = ("title", "status", "eta", "position", "is_published", "updated_at")
    list_editable = ("status", "eta", "position", "is_published")
    list_filter = ("status", "is_published")
    search_fields = ("title", "body")
    ordering = ("position", "created_at")


@admin.register(ChangelogEntry)
class ChangelogEntryAdmin(ModelAdmin):
    list_display = ("date", "kind", "title_en", "is_published", "digest")
    list_editable = ("is_published",)
    list_filter = ("kind", "is_published")
    search_fields = ("title_en", "title_ru", "slug")
    readonly_fields = ("slug", "created_at", "digest")
    ordering = ("-date", "-created_at")
