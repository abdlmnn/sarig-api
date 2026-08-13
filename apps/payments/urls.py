from django.urls import path
from .views import PaymentMethodsView, PayMongoWebhookView

urlpatterns = [
    path("methods/", PaymentMethodsView.as_view(), name="payment_methods"),
    path("webhooks/paymongo/", PayMongoWebhookView.as_view(), name="paymongo_webhook"),
]
