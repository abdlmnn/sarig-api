import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from apps.orders.routing import websocket_urlpatterns as order_ws
from apps.chat.routing import websocket_urlpatterns as chat_ws
from apps.rides.routing import websocket_urlpatterns as rides_ws
from apps.common.routing import websocket_urlpatterns as realtime_ws
from config.jwt_auth_middleware import JWTAuthMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(JWTAuthMiddleware(
        URLRouter(
            order_ws + chat_ws + rides_ws + realtime_ws
        )
    )),
})
