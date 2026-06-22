from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from apps.users.views import LogoutView
from apps.onboarding.views import (
    AccountSetupView,
    AdminApplicationDetailView,
    AdminApplicationListView,
    AdminApproveApplicationView,
    AdminDocumentView,
    AdminRejectApplicationView,
    AdminRequestChangesView,
)

app_name = "v1"

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
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
]
