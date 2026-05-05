from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ReviewQueueView,
    SubmissionViewSet,
    VerdictOverrideView,
    WidgetEmbedView,
)

router = DefaultRouter()
router.register("submissions", SubmissionViewSet, basename="submission")

urlpatterns = [
    path("", include(router.urls)),
    path("widget/embed/<str:sha256>/", WidgetEmbedView.as_view(), name="widget-embed"),
    path("review/queue/", ReviewQueueView.as_view(), name="review-queue"),
    path("review/<uuid:id>/override/", VerdictOverrideView.as_view(), name="review-override"),
]
