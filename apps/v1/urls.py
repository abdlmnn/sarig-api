from django.urls import path, include
import importlib
import importlib.util
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = "v1"

def include_if_exists(module_path):
    spec = importlib.util.find_spec(module_path)
    if spec is not None:
        return [path(module_path.split('.')[1] + "/", include(module_path))]
    return []

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

# Add optional apps if they exist in the current branch
optional_apps = ["apps.marketing.urls", "apps.chat.urls", "apps.reviews.urls"]
for app_url in optional_apps:
    urlpatterns += include_if_exists(app_url)
