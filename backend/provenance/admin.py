from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ProvenanceResult


@admin.register(ProvenanceResult)
class ProvenanceResultAdmin(ModelAdmin):
    list_display = ("submission", "source_type", "title", "similarity_score", "found_at")
    list_filter = ("source_type",)
    readonly_fields = ("id", "found_at")
    raw_id_fields = ("submission",)
