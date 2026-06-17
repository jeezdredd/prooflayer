from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AnalyzeUrlView,
    PublicFeedView,
    PublicSubmissionDetailView,
    ReviewQueueView,
    SubmissionStatusView,
    SubmissionViewSet,
    VerdictOverrideView,
    WidgetEmbedView,
)

router = DefaultRouter()
router.register("submissions", SubmissionViewSet, basename="submission")

urlpatterns = [
    path("", include(router.urls)),
    path("feed/", PublicFeedView.as_view(), name="public-feed"),
    path("feed/<uuid:id>/", PublicSubmissionDetailView.as_view(), name="public-submission-detail"),
    path("widget/embed/<str:sha256>/", WidgetEmbedView.as_view(), name="widget-embed"),
    path("review/queue/", ReviewQueueView.as_view(), name="review-queue"),
    path("review/<uuid:id>/override/", VerdictOverrideView.as_view(), name="review-override"),
    path("analyze-url/", AnalyzeUrlView.as_view(), name="analyze-url"),
    path("submissions/<uuid:id>/status/", SubmissionStatusView.as_view(), name="submission-status"),
]
