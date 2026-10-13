from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ClassroomViewSet, JoinClassroomView

router = DefaultRouter()
router.register("classrooms", ClassroomViewSet, basename="classroom")

urlpatterns = [
    path("join/", JoinClassroomView.as_view(), name="classroom-join"),
    path("", include(router.urls)),
]
