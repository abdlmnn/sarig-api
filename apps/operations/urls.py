from django.urls import path

from .views import (
    AdminAlertListView,
    AdminAlertResolveView,
    AdminDashboardView,
    AdminFinanceOverviewView,
    AdminMarketingOverviewView,
    AdminMerchantListView,
    AdminRiderListView,
    ServiceZoneActivityView,
    ServiceZoneDetailView,
    ServiceZoneListView,
    ServiceZoneMerchantsView,
    ServiceZoneRidersView,
)


app_name = "operations"

urlpatterns = [
    path("dashboard", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("service-zones/", ServiceZoneListView.as_view(), name="admin-service-zones"),
    path("service-zones/<uuid:zone_id>/", ServiceZoneDetailView.as_view(), name="admin-service-zone-detail"),
    path("service-zones/<uuid:zone_id>/merchants/", ServiceZoneMerchantsView.as_view(), name="admin-service-zone-merchants"),
    path("service-zones/<uuid:zone_id>/riders/", ServiceZoneRidersView.as_view(), name="admin-service-zone-riders"),
    path("service-zones/<uuid:zone_id>/activity/", ServiceZoneActivityView.as_view(), name="admin-service-zone-activity"),
    path("merchants", AdminMerchantListView.as_view(), name="admin-merchants"),
    path("riders", AdminRiderListView.as_view(), name="admin-riders"),
    path("finance/overview", AdminFinanceOverviewView.as_view(), name="admin-finance-overview"),
    path("marketing/overview", AdminMarketingOverviewView.as_view(), name="admin-marketing-overview"),
    path("system/alerts", AdminAlertListView.as_view(), name="admin-alerts"),
    path("system/alerts/<uuid:alert_id>/resolve", AdminAlertResolveView.as_view(), name="admin-alert-resolve"),
]
