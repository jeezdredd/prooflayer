from django.urls import path

from .views import ProvenanceListView

urlpatterns = [
    path("<uuid:submission_id>/", ProvenanceListView.as_view(), name="provenance-list"),
]
