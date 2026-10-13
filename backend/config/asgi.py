import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.conf import settings
from content.routing import websocket_urlpatterns
from content.ws_auth import JWTAuthMiddleware, ws_allowed_origins

application = ProtocolTypeRouter({
    "http": django_asgi,
    "websocket": OriginValidator(
        JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
        ws_allowed_origins(settings),
    ),
})
