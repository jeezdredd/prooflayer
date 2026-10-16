from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .batch_views import BatchViewSet
from .objections import ObjectionListView, ObjectionRespondView, SubmissionObjectionView
from .views import (
    AnalyzeUrlView,
    PublicFeedView,
    PublicSubmissionDetailView,
    ReviewQueueView,
    SubmissionStatusView,
    SubmissionViewSet,
    VerdictOverrideView,
)

router = DefaultRouter()
router.register("submissions", SubmissionViewSet, basename="submission")
router.register("batches", BatchViewSet, basename="batch")

urlpatterns = [
    path("", include(router.urls)),
    path("feed/", PublicFeedView.as_view(), name="public-feed"),
    path("feed/<uuid:id>/", PublicSubmissionDetailView.as_view(), name="public-submission-detail"),
    path("review/queue/", ReviewQueueView.as_view(), name="review-queue"),
    path("review/<uuid:id>/override/", VerdictOverrideView.as_view(), name="review-override"),
    path("analyze-url/", AnalyzeUrlView.as_view(), name="analyze-url"),
    path("submissions/<uuid:id>/status/", SubmissionStatusView.as_view(), name="submission-status"),
    path("submissions/<uuid:id>/objection/", SubmissionObjectionView.as_view(), name="submission-objection"),
    path("objections/", ObjectionListView.as_view(), name="objection-list"),
    path("objections/<uuid:id>/respond/", ObjectionRespondView.as_view(), name="objection-respond"),
]
