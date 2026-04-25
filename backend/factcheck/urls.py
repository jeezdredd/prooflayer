from django.urls import path

from .views import FactCheckView

urlpatterns = [
    path("check/", FactCheckView.as_view(), name="factcheck"),
]
