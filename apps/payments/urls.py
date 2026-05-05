from django.urls import path
from .views import PayMongoWebhookView

urlpatterns = [
    path("webhooks/paymongo/", PayMongoWebhookView.as_view(), name="paymongo_webhook"),
]
