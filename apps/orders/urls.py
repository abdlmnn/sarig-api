from django.urls import path
from .views import CheckoutQuoteView, CheckoutView, CustomerOrderDetailView, MerchantOrderActionView, MerchantOrderDetailView, MerchantOrderListView, MerchantStoreOrderAnalyticsView, OrderDeliveryRouteView, PrescriptionFileView, StoreOrderActivityView
from .cart_views import (
    CustomerCartItemView,
    CustomerCartListView,
    CustomerCartSyncView,
    CustomerStoreCartView,
)

urlpatterns = [
    path("prescriptions/<uuid:prescription_id>/file/", PrescriptionFileView.as_view(), name="prescription-file"),
    path("carts/", CustomerCartListView.as_view(), name="customer-cart-list"),
    path("carts/sync/", CustomerCartSyncView.as_view(), name="customer-cart-sync"),
    path("carts/items/<uuid:product_id>/", CustomerCartItemView.as_view(), name="customer-cart-item"),
    path("carts/stores/<uuid:store_id>/", CustomerStoreCartView.as_view(), name="customer-store-cart"),
    path("store-activity/", StoreOrderActivityView.as_view(), name="store-order-activity"),
    path("merchant/", MerchantOrderListView.as_view(), name="merchant-order-list"),
    path("merchant/stores/<uuid:store_id>/analytics/", MerchantStoreOrderAnalyticsView.as_view(), name="merchant-store-order-analytics"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("checkout/quote/", CheckoutQuoteView.as_view(), name="checkout-quote"),
    path("<uuid:order_id>/", CustomerOrderDetailView.as_view(), name="customer-order-detail"),
    path("<uuid:order_id>/delivery-route/", OrderDeliveryRouteView.as_view(), name="order-delivery-route"),
    path("<uuid:order_id>/merchant-detail/", MerchantOrderDetailView.as_view(), name="merchant-order-detail"),
    path("<uuid:order_id>/action/", MerchantOrderActionView.as_view(), name="merchant-order-action"),
]
