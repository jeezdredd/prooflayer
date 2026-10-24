from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import PlagiarismReport


@admin.register(PlagiarismReport)
class PlagiarismReportAdmin(ModelAdmin):
    list_display = ("submission", "status", "originality", "web_status", "updated_at")
    list_filter = ("status", "web_status")
    readonly_fields = ("submission", "matches", "error")
