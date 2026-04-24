from django.urls import path

from .views import ReportCreateView, ReportListView

urlpatterns = [
    path("", ReportCreateView.as_view(), name="report-create"),
    path("admin/", ReportListView.as_view(), name="report-list"),
]
