from django.urls import path

from .views import FactCheckStatusView, FactCheckView

urlpatterns = [
    path("check/", FactCheckView.as_view(), name="factcheck"),
    path("status/<str:task_id>/", FactCheckStatusView.as_view(), name="factcheck-status"),
]
