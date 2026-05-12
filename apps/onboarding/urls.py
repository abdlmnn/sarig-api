from django.urls import path
from .views import (
    MerchantApplicationCreateView,
    MerchantApplicationDetailView,
    RiderApplicationCreateView,
    RiderApplicationDetailView,
)

urlpatterns = [
    path("merchant/apply/", MerchantApplicationCreateView.as_view(), name="merchant-apply"),
    path("merchant/status/<uuid:pk>/", MerchantApplicationDetailView.as_view(), name="merchant-status"),
    path("rider/apply/", RiderApplicationCreateView.as_view(), name="rider-apply"),
    path("rider/status/<uuid:pk>/", RiderApplicationDetailView.as_view(), name="rider-status"),
]
