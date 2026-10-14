from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from rest_framework.routers import SimpleRouter

from api.changelog_views import ChangelogView
from api.roadmap_views import RoadmapItemViewSet
from api.system_views import RecordVisitView, SystemStatusView, FeedbackView

roadmap_router = SimpleRouter()
roadmap_router.register("api/v1/system/roadmap", RoadmapItemViewSet, basename="roadmap")


def health(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("users.urls")),
    path("api/v1/content/", include("content.urls")),
    path("api/v1/analyzers/", include("analyzers.urls")),
    path("api/v1/crowdsource/", include("crowdsource.urls")),
    path("api/v1/reports/", include("reports.urls")),
    path("api/v1/provenance/", include("provenance.urls")),
    path("api/v1/factcheck/", include("factcheck.urls")),
    path("api/v1/billing/", include("billing.urls")),
    path("api/v1/classroom/", include("classroom.urls")),
    path("api/v1/auth/health/", health),
    path("api/v1/system/status/", SystemStatusView.as_view(), name="system-status"),
    path("api/v1/system/visit/", RecordVisitView.as_view(), name="system-visit"),
    path("api/v1/system/feedback/", FeedbackView.as_view(), name="system-feedback"),
    path("api/v1/system/changelog/", ChangelogView.as_view(), name="system-changelog"),
    *roadmap_router.urls,
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
