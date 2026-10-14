from datetime import timedelta
from io import StringIO
from typing import Any

from django.contrib import admin, messages
from django.core.management import call_command
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString
from unfold.admin import ModelAdmin
from unfold.decorators import action, display

from analyzers import auto_retrain
from analyzers.roster import describe_drift, expected_roster, roster_drift
from analyzers.tasks import run_weekly_retrain
from common.admin_tools import SuperuserActionsAdmin

from .models import AnalysisResult, AnalyzerConfig, RetrainRun, TrainingSample
from .retrain_report import STATUS_VARIANTS, holdout_rows, holdout_summary

RETRAIN_RUNNING_WINDOW = timedelta(hours=6)
REASON_PREVIEW = 90


@admin.register(AnalyzerConfig)
class AnalyzerConfigAdmin(SuperuserActionsAdmin):
    list_display = ("name", "is_active", "weight", "expected_weight", "roster_state", "version", "queue", "timeout")
    list_display_links = ("name",)
    list_editable = ("is_active", "weight")
    list_filter = ("is_active", "queue")
    search_fields = ("name", "analyzer_class")
    ordering = ("-is_active", "-weight", "name")
    readonly_fields = ("created_at",)
    list_before_template = "admin/analyzers/roster_notice.html"
    actions_list = ["sync_roster"]

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        report = roster_drift()
        extra_context = {**(extra_context or {}), "roster_report": report, "roster_drift_text": describe_drift(report)}
        return super().changelist_view(request, extra_context=extra_context)

    @display(description="Weight in code")
    def expected_weight(self, obj: AnalyzerConfig) -> str:
        spec = expected_roster().get(obj.name)
        return "-" if spec is None else f"{float(spec['weight']):g}"

    @display(
        description="Roster",
        label={"in sync": "success", "weight differs": "warning", "inactive": "warning", "not in code": "danger"},
    )
    def roster_state(self, obj: AnalyzerConfig) -> str:
        spec = expected_roster().get(obj.name)
        if spec is None:
            return "not in code" if obj.is_active else "inactive"
        if not obj.is_active:
            return "inactive"
        if abs(obj.weight - float(spec["weight"])) > 1e-6:
            return "weight differs"
        return "in sync"

    @action(description="Reset roster to code", icon="restart_alt", permissions=["superuser"], url_path="sync-roster")
    def sync_roster(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            return self.confirm_action(
                request,
                title="Reset analyzer roster to code",
                message=(
                    "Weights, active flags and versions return to the values in seed_analyzers. "
                    "Manual edits made here are lost. The backend does the same on every boot."
                ),
                button="Reset roster",
                danger=True,
            )
        call_command("seed_analyzers", stdout=StringIO())
        self.message_user(request, "Analyzer roster reset to the values in code.", messages.SUCCESS)
        return self.back_to_changelist()


@admin.register(AnalysisResult)
class AnalysisResultAdmin(ModelAdmin):
    list_display = ("id", "submission", "analyzer", "confidence", "verdict", "execution_time", "created_at")
    list_filter = ("verdict", "analyzer")
    list_select_related = ("submission", "analyzer")
    raw_id_fields = ("submission",)
    readonly_fields = ("evidence",)


@admin.register(TrainingSample)
class TrainingSampleAdmin(ModelAdmin):
    list_display = ("created_at", "media_type", "label_badge", "mime_type", "source_ref", "source_submission")
    list_filter = ("label", "media_type")
    search_fields = ("sha256", "source_ref", "source_submission")
    readonly_fields = (
        "id", "file", "media_type", "mime_type", "label", "sha256", "source_ref", "source_submission", "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @display(description="Label", ordering="label", label={"real": "success", "fake": "danger"})
    def label_badge(self, obj: TrainingSample) -> str:
        return obj.label


@admin.register(RetrainRun)
class RetrainRunAdmin(SuperuserActionsAdmin):
    list_display = (
        "started_at", "media_type", "status_badge", "decision", "samples_used", "holdout_brief", "duration",
        "triggered_by",
    )
    list_filter = ("status", "media_type", "started_at")
    list_select_related = ("triggered_by",)
    ordering = ("-started_at",)
    date_hierarchy = "started_at"
    list_before_template = "admin/analyzers/retrain_notice.html"
    actions_list = ["run_retrain_now", "rollback_detector"]
    fieldsets = (
        (
            "Decision",
            {
                "fields": (
                    "status", "error", "problems", "media_type", "samples_used", "sources", "epochs", "hf_revision",
                ),
            },
        ),
        ("Held-out set", {"fields": ("holdout_table", "knots")}),
        ("Run", {"fields": ("id", "triggered_by", "started_at", "finished_at", "duration", "metrics")}),
    )
    readonly_fields = (
        "id", "media_type", "samples_used", "epochs", "hf_revision", "status", "error", "problems", "sources",
        "holdout_table", "knots", "metrics", "triggered_by", "started_at", "finished_at", "duration",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: RetrainRun | None = None) -> bool:
        return False

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        extra_context = {
            **(extra_context or {}),
            "retrain_state": {
                "pool": auto_retrain.image_count(auto_retrain.POOL),
                "calibration": auto_retrain.image_count(auto_retrain.CALIBRATION),
                "holdout": auto_retrain.image_count(auto_retrain.HOLDOUT),
                "rollback_available": auto_retrain.PREVIOUS.exists(),
                "running": self._running().exists(),
            },
        }
        return super().changelist_view(request, extra_context=extra_context)

    def _running(self) -> QuerySet[RetrainRun]:
        return RetrainRun.objects.filter(
            status=RetrainRun.Status.STARTED, started_at__gte=timezone.now() - RETRAIN_RUNNING_WINDOW,
        )

    @display(description="Status", ordering="status", label=STATUS_VARIANTS)
    def status_badge(self, obj: RetrainRun) -> str:
        return obj.status

    @display(description="Decision")
    def decision(self, obj: RetrainRun) -> str:
        if obj.status == RetrainRun.Status.SUCCESS:
            return "promoted"
        if obj.status == RetrainRun.Status.STARTED:
            return "running"
        reason = obj.error or "-"
        return reason if len(reason) <= REASON_PREVIEW else reason[:REASON_PREVIEW].rstrip() + "..."

    @display(description="Held-out")
    def holdout_brief(self, obj: RetrainRun) -> str:
        return holdout_summary(obj.metrics) or "-"

    @display(description="Duration")
    def duration(self, obj: RetrainRun) -> str:
        if not obj.finished_at:
            return "-"
        seconds = int((obj.finished_at - obj.started_at).total_seconds())
        hours, rest = divmod(seconds, 3600)
        minutes = rest // 60
        return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m {seconds % 60:02d}s"

    @display(description="Held-out numbers")
    def holdout_table(self, obj: RetrainRun) -> SafeString:
        return render_to_string("admin/dashboard/holdout_table.html", {"rows": holdout_rows(obj.metrics)})

    @display(description="Gate problems")
    def problems(self, obj: RetrainRun) -> str:
        return "; ".join((obj.metrics or {}).get("problems") or []) or "-"

    @display(description="New data")
    def sources(self, obj: RetrainRun) -> str:
        metrics = obj.metrics or {}
        if "fetched" not in metrics and "db_samples" not in metrics:
            return "-"
        return f"{metrics.get('fetched', 0)} fetched, {metrics.get('db_samples', 0)} labelled by users"

    @display(description="Calibration knots")
    def knots(self, obj: RetrainRun) -> str:
        knots = (obj.metrics or {}).get("knots") or []
        if not knots:
            return "-"
        return format_html("<code>{}</code>", ", ".join(f"{raw:.3f}→{mapped:.2f}" for raw, mapped in knots))

    @action(description="Run retrain now", icon="model_training", permissions=["superuser"], url_path="run-retrain")
    def run_retrain_now(self, request: HttpRequest) -> HttpResponse:
        if self._running().exists():
            self.message_user(request, "A retrain is already running; wait for it to finish.", messages.WARNING)
            return self.back_to_changelist()
        if request.method != "POST":
            return self.confirm_action(
                request,
                title="Run the image retrain now",
                message=(
                    "Queues the same gated job the weekly schedule runs: fetch new data, fine-tune a candidate, "
                    "compare it with the live model on the held-out set and promote it only if it is better. "
                    "It can take several hours and loads the GPU worker."
                ),
                button="Queue retrain",
                details=[
                    {"label": "Training pool images", "value": auto_retrain.image_count(auto_retrain.POOL)},
                    {"label": "Held-out images", "value": auto_retrain.image_count(auto_retrain.HOLDOUT)},
                ],
            )
        run_weekly_retrain.delay("image", triggered_by_id=request.user.id)
        self.message_user(
            request, "Retrain queued. A new run appears here once the worker picks it up.", messages.SUCCESS,
        )
        return self.back_to_changelist()

    @action(description="Roll back image detector", icon="undo", permissions=["superuser"], url_path="rollback")
    def rollback_detector(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            available = auto_retrain.PREVIOUS.exists()
            return self.confirm_action(
                request,
                title="Roll back the image detector",
                message=(
                    "Swaps the live image model with the one kept by the last promotion. "
                    "Running the rollback again swaps them back. "
                    "Workers load the swapped model on their next image check."
                ),
                button="Roll back",
                danger=True,
                details=[
                    {
                        "label": "Previous model",
                        "value": "kept" if available else "none",
                        "variant": "success" if available else "warning",
                    },
                ],
            )
        try:
            auto_retrain.rollback()
        except (RuntimeError, OSError) as exc:
            self.message_user(request, f"Rollback failed: {exc}", messages.ERROR)
        else:
            self.message_user(request, "Image detector rolled back to the previous model.", messages.SUCCESS)
        return self.back_to_changelist()
