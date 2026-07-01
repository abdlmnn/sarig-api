from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StoreViewSet, BusinessVerticalViewSet, MerchantAnalyticsView, NearbyStoresView

router = DefaultRouter()

router.register(r"stores", StoreViewSet, basename="stores")
router.register(r"verticals", BusinessVerticalViewSet, basename="verticals")
router.register(r"business-verticals", BusinessVerticalViewSet, basename="business-verticals")

urlpatterns = [
    path("", include(router.urls)),
    path("stores/<uuid:store_id>/analytics/", MerchantAnalyticsView.as_view(), name="store-analytics"),
    path("nearby/", NearbyStoresView.as_view(), name="nearby-stores"),
]
