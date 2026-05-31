from django.contrib import admin

from .models import AnalyzerConfig, AnalysisResult, RetrainRun


@admin.register(AnalyzerConfig)
class AnalyzerConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "weight", "queue", "timeout")
    list_filter = ("is_active", "queue")


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "analyzer", "confidence", "verdict", "execution_time", "created_at")
    list_filter = ("verdict", "analyzer")
    readonly_fields = ("evidence",)


@admin.register(RetrainRun)
class RetrainRunAdmin(admin.ModelAdmin):
    list_display = ("media_type", "status", "samples_used", "epochs", "hf_revision", "started_at", "finished_at")
    list_filter = ("status", "media_type")
    readonly_fields = ("id", "media_type", "samples_used", "epochs", "hf_revision", "status", "error", "started_at", "finished_at")
    ordering = ("-started_at",)
