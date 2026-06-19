from django.urls import path

from .views import (
    AnalysisResultListView,
    AnalyzerConfigListView,
    RetrainStatusView,
    RetrainTriggerView,
)

urlpatterns = [
    path("configs/", AnalyzerConfigListView.as_view(), name="analyzer-configs"),
    path("results/<uuid:submission_id>/", AnalysisResultListView.as_view(), name="analysis-results"),
    path("retrain/", RetrainTriggerView.as_view(), name="retrain-trigger"),
    path("retrain/runs/", RetrainStatusView.as_view(), name="retrain-runs"),
]
