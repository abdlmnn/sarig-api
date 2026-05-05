from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/merchant/(?P<store_id>[^/]+)/$", consumers.MerchantOrderConsumer.as_asgi()),
]
