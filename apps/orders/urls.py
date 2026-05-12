from django.urls import path
from .views import CheckoutView, MerchantOrderActionView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("<uuid:order_id>/action/", MerchantOrderActionView.as_view(), name="merchant-order-action"),
]
