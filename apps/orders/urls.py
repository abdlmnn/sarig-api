from django.urls import path
from .views import CheckoutView, MerchantOrderActionView, MerchantStoreOrderAnalyticsView, StoreOrderActivityView

urlpatterns = [
    path("store-activity/", StoreOrderActivityView.as_view(), name="store-order-activity"),
    path("merchant/stores/<uuid:store_id>/analytics/", MerchantStoreOrderAnalyticsView.as_view(), name="merchant-store-order-analytics"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("<uuid:order_id>/action/", MerchantOrderActionView.as_view(), name="merchant-order-action"),
]
