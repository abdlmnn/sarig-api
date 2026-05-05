from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = "v1"

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("users/", include("apps.users.urls")),
    path("vendors/", include("apps.vendors.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("orders/", include("apps.orders.urls")),
    path("payments/", include("apps.payments.urls")),
    path("onboarding/", include("apps.onboarding.urls")),
    path("riders/", include("apps.riders.urls")),
]
