from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BusinessVerticalViewSet,
    MerchantDashboardOverviewView,
    MerchantStoreBrandingDetailView,
    MerchantStoreBrandingListView,
    MerchantStoreStatusView,
    NearbyStoresView,
    StoreViewSet,
)

router = DefaultRouter()

router.register(r"stores", StoreViewSet, basename="stores")
router.register(r"business-verticals", BusinessVerticalViewSet, basename="business-verticals")

urlpatterns = [
    path("dashboard/overview/", MerchantDashboardOverviewView.as_view(), name="merchant-dashboard-overview"),
    path("store/branding/", MerchantStoreBrandingListView.as_view(), name="merchant-store-branding-list"),
    path(
        "store/branding/<uuid:store_id>/",
        MerchantStoreBrandingDetailView.as_view(),
        name="merchant-store-branding-detail",
    ),
    path("store/status/", MerchantStoreStatusView.as_view(), name="merchant-store-status"),
    path("nearby/", NearbyStoresView.as_view(), name="nearby-stores"),
    path("", include(router.urls)),
]
