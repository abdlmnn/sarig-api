from django.urls import re_path

from .consumers import RideConsumer


websocket_urlpatterns = [
    re_path(r"ws/rides/$", RideConsumer.as_asgi()),
]

