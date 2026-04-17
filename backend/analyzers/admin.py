from django.contrib import admin

from .models import AnalyzerConfig, AnalysisResult


@admin.register(AnalyzerConfig)
class AnalyzerConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "weight", "queue", "timeout")
    list_filter = ("is_active", "queue")


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "analyzer", "confidence", "verdict", "execution_time", "created_at")
    list_filter = ("verdict", "analyzer")
    readonly_fields = ("evidence",)
