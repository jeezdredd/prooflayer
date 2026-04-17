from django.urls import path

from .views import AnalyzerConfigListView, AnalysisResultListView

urlpatterns = [
    path("configs/", AnalyzerConfigListView.as_view(), name="analyzer-configs"),
    path("results/<uuid:submission_id>/", AnalysisResultListView.as_view(), name="analysis-results"),
]
