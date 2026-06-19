from django.urls import path

from .views import (
    FactCheckExportView,
    FactCheckExtractDocView,
    FactCheckFetchUrlView,
    FactCheckStatusView,
    FactCheckView,
)

urlpatterns = [
    path("check/", FactCheckView.as_view(), name="factcheck"),
    path("status/<str:task_id>/", FactCheckStatusView.as_view(), name="factcheck-status"),
    path("export/", FactCheckExportView.as_view(), name="factcheck-export"),
    path("fetch-url/", FactCheckFetchUrlView.as_view(), name="factcheck-fetch-url"),
    path("extract-doc/", FactCheckExtractDocView.as_view(), name="factcheck-extract-doc"),
]
