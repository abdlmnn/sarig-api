from django.urls import path

from .views import (
    DeliveryFeeEstimateView,
    LocationSearchView,
    ReverseGeocodeView,
    RouteEstimateView,
)


urlpatterns = [
    path("search/", LocationSearchView.as_view(), name="location-search"),
    path("reverse/", ReverseGeocodeView.as_view(), name="location-reverse"),
    path("route-estimate/", RouteEstimateView.as_view(), name="location-route-estimate"),
    path("delivery-fee-estimate/", DeliveryFeeEstimateView.as_view(), name="location-delivery-fee-estimate"),
]
