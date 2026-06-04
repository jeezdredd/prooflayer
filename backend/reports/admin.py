from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Report


@admin.register(Report)
class ReportAdmin(ModelAdmin):
    list_display = ("id", "reporter", "submission", "reason", "status", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("description",)
    readonly_fields = ("reporter", "submission", "reason", "description", "created_at")
    list_editable = ("status",)
