from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from apps.users.views import AdminLoginView, LogoutView, MerchantLoginView
from apps.vendors.views import MerchantDashboardOverviewView, MerchantStoreStatusView
from apps.onboarding.views import (
    AccountSetupView,
    AdminApplicationDetailView,
    AdminApplicationListView,
    AdminApproveApplicationView,
    AdminDocumentView,
    AdminRejectApplicationView,
    AdminRequestChangesView,
)
from apps.catalog.views import MerchantProductListView
from apps.vendors.views import MerchantDashboardOverviewView, MerchantStoreStatusView

app_name = "v1"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_scope = "auth"


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_scope = "auth"


urlpatterns = [
    path("auth/token/", ThrottledTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", ThrottledTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/admin/login/", AdminLoginView.as_view(), name="admin_login"),
    path("auth/merchant/login/", MerchantLoginView.as_view(), name="merchant_login"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    path("merchant/dashboard/overview/", MerchantDashboardOverviewView.as_view(), name="merchant-dashboard-overview"),
    path("merchant/store/status/", MerchantStoreStatusView.as_view(), name="merchant-store-status"),
    path("accounts/setup/<uuid:token>/", AccountSetupView.as_view(), name="account-setup"),
    path("admin/onboarding/applications/", AdminApplicationListView.as_view(), name="admin-onboarding-applications"),
    path("admin/onboarding/applications/<str:application_id>/", AdminApplicationDetailView.as_view(), name="admin-onboarding-application-detail"),
    path("admin/onboarding/applications/<str:application_id>/documents/<str:document_key>/", AdminDocumentView.as_view(), name="admin-onboarding-application-document"),
    path("admin/onboarding/applications/<str:application_id>/approve/", AdminApproveApplicationView.as_view(), name="admin-onboarding-application-approve"),
    path("admin/onboarding/applications/<str:application_id>/request-changes/", AdminRequestChangesView.as_view(), name="admin-onboarding-application-request-changes"),
    path("admin/onboarding/applications/<str:application_id>/reject/", AdminRejectApplicationView.as_view(), name="admin-onboarding-application-reject"),
    path("admin/", include("apps.operations.urls")),
    path("users/", include("apps.users.urls")),
    path("vendors/", include("apps.vendors.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("orders/", include("apps.orders.urls")),
    path("payments/", include("apps.payments.urls")),
    path("onboarding/", include("apps.onboarding.urls")),
    path("riders/", include("apps.riders.urls")),
    path("marketing/", include("apps.marketing.urls")),
    path("chat/", include("apps.chat.urls")),
    path("reviews/", include("apps.reviews.urls")),
    path("rides/", include("apps.rides.urls")),
    path("locations/", include("apps.locations.urls")),
    path("merchant/dashboard/overview/", MerchantDashboardOverviewView.as_view(), name="merchant-dashboard-overview"),
    path("merchant/products/", MerchantProductListView.as_view(), name="merchant-products"),
    path("merchant/store/status/", MerchantStoreStatusView.as_view(), name="merchant-store-status"),
]
