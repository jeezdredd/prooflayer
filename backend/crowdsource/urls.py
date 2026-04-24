from django.urls import path

from .views import VoteCreateView, VoteStatsView

urlpatterns = [
    path("votes/", VoteCreateView.as_view(), name="vote-create"),
    path("votes/stats/<uuid:submission_id>/", VoteStatsView.as_view(), name="vote-stats"),
]
