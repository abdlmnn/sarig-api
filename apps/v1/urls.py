from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from apps.users.serializers import (
    LegacyTokenObtainPairSerializer,
    LegacyTokenRefreshSerializer,
)
from apps.users.views import (
    AdminCookieLoginView,
    AdminCookieLogoutView,
    AdminCookieRefreshView,
    CsrfBootstrapView,
    LoginView,
    LogoutView,
    MerchantCookieLoginView,
    MerchantCookieLogoutView,
    MerchantCookieRefreshView,
)

app_name = "v1"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_scope = "auth"
    serializer_class = LegacyTokenObtainPairSerializer


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_scope = "auth"
    serializer_class = LegacyTokenRefreshSerializer


urlpatterns = [
    path("auth/csrf/", CsrfBootstrapView.as_view(), name="auth_csrf"),
    path("auth/admin/login/", AdminCookieLoginView.as_view(), name="admin_cookie_login"),
    path("auth/admin/refresh/", AdminCookieRefreshView.as_view(), name="admin_cookie_refresh"),
    path("auth/admin/logout/", AdminCookieLogoutView.as_view(), name="admin_cookie_logout"),
    path("auth/merchant/login/", MerchantCookieLoginView.as_view(), name="merchant_cookie_login"),
    path("auth/merchant/refresh/", MerchantCookieRefreshView.as_view(), name="merchant_cookie_refresh"),
    path("auth/merchant/logout/", MerchantCookieLogoutView.as_view(), name="merchant_cookie_logout"),
    path("auth/token/", ThrottledTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", ThrottledTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    path("operations/", include("apps.operations.urls")),
    path("merchant/", include("apps.vendors.urls")),
    path("users/", include("apps.users.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("orders/", include("apps.orders.urls")),
    path("payments/", include("apps.payments.urls")),
    path("email-templates/", include("apps.email_templates.urls")),
    path("onboarding/", include("apps.onboarding.urls")),
    path("riders/", include("apps.riders.urls")),
    path("marketing/", include("apps.marketing.urls")),
    path("chat/", include("apps.chat.urls")),
    path("reviews/", include("apps.reviews.urls")),
    path("rides/", include("apps.rides.urls")),
    path("locations/", include("apps.locations.urls")),
]
