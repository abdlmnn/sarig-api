from django.urls import path
from .views import RiderStatusToggleView, RiderLocationUpdateView, RiderOrderActionView, RiderDashboardView

urlpatterns = [
    path("status/toggle/", RiderStatusToggleView.as_view(), name="rider-status-toggle"),
    path("location/update/", RiderLocationUpdateView.as_view(), name="rider-location-update"),
    path("orders/<uuid:order_id>/action/", RiderOrderActionView.as_view(), name="rider-order-action"),
    path("dashboard/", RiderDashboardView.as_view(), name="rider-dashboard"),
]
