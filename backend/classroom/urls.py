from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .org_views import (
    ClassroomHubView,
    OrganizationClassesView,
    OrganizationDetailView,
    OrganizationJoinTeacherView,
    OrganizationListView,
    OrganizationRotateCodeView,
    OrganizationSettingsView,
    OrganizationTeachersView,
)
from .views import ClassroomViewSet, JoinClassroomView

router = DefaultRouter()
router.register("classrooms", ClassroomViewSet, basename="classroom")

urlpatterns = [
    path("join/", JoinClassroomView.as_view(), name="classroom-join"),
    path("hub/", ClassroomHubView.as_view(), name="classroom-hub"),
    path("orgs/", OrganizationListView.as_view(), name="org-list"),
    path("orgs/<slug:slug>/", OrganizationDetailView.as_view(), name="org-detail"),
    path("orgs/<slug:slug>/join-teacher/", OrganizationJoinTeacherView.as_view(), name="org-join-teacher"),
    path("orgs/<slug:slug>/rotate-teacher-code/", OrganizationRotateCodeView.as_view(), name="org-rotate-code"),
    path("orgs/<slug:slug>/settings/", OrganizationSettingsView.as_view(), name="org-settings"),
    path("orgs/<slug:slug>/teachers/", OrganizationTeachersView.as_view(), name="org-teachers"),
    path("orgs/<slug:slug>/teachers/<int:user_id>/", OrganizationTeachersView.as_view(), name="org-teacher-detail"),
    path("orgs/<slug:slug>/classes/", OrganizationClassesView.as_view(), name="org-classes"),
    path("", include(router.urls)),
]
