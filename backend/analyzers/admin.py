from django.contrib import admin

from unfold.admin import ModelAdmin

from .models import AnalysisResult, AnalyzerConfig, RetrainRun


@admin.register(AnalyzerConfig)
class AnalyzerConfigAdmin(ModelAdmin):
    list_display = ("name", "version", "is_active", "weight", "queue", "timeout")
    list_filter = ("is_active", "queue")


@admin.register(AnalysisResult)
class AnalysisResultAdmin(ModelAdmin):
    list_display = ("id", "submission", "analyzer", "confidence", "verdict", "execution_time", "created_at")
    list_filter = ("verdict", "analyzer")
    readonly_fields = ("evidence",)


@admin.register(RetrainRun)
class RetrainRunAdmin(ModelAdmin):
    list_display = ("media_type", "status", "samples_used", "epochs", "hf_revision", "started_at", "finished_at")
    list_filter = ("status", "media_type")
    readonly_fields = ("id", "media_type", "samples_used", "epochs", "hf_revision", "status", "error", "started_at", "finished_at")
    ordering = ("-started_at",)
