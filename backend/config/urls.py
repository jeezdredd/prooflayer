from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("users.urls")),
    path("api/v1/content/", include("content.urls")),
    path("api/v1/analyzers/", include("analyzers.urls")),
    path("api/v1/crowdsource/", include("crowdsource.urls")),
    path("api/v1/reports/", include("reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
