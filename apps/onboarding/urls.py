from django.urls import path

from .views import (
    AccountSetupView,
    AdminApplicationDetailView,
    AdminApplicationListView,
    AdminApproveApplicationView,
    AdminDocumentView,
    AdminRejectApplicationView,
    AdminRequestChangesView,
    ApplicationEditTokenView,
    MerchantApplicationCreateView,
    MerchantApplicationDetailView,
    MerchantOnboardingOptionsView,
    MerchantStatusCheckView,
    RiderApplicationCreateView,
    RiderApplicationDetailView,
    RiderStatusCheckView,
)

urlpatterns = [
    path("merchant/options/", MerchantOnboardingOptionsView.as_view(), name="merchant-onboarding-options"),
    path("merchant/apply/", MerchantApplicationCreateView.as_view(), name="merchant-apply"),
    path("merchant/status/check/", MerchantStatusCheckView.as_view(), name="merchant-status-check"),
    path("merchant/status/<uuid:pk>/", MerchantApplicationDetailView.as_view(), name="merchant-status"),
    path("rider/apply/", RiderApplicationCreateView.as_view(), name="rider-apply"),
    path("rider/status/check/", RiderStatusCheckView.as_view(), name="rider-status-check"),
    path("rider/status/<uuid:pk>/", RiderApplicationDetailView.as_view(), name="rider-status"),
    path("applications/edit/<uuid:token>/", ApplicationEditTokenView.as_view(), name="onboarding-application-edit"),
    path("accounts/setup/<uuid:token>/", AccountSetupView.as_view(), name="account-setup"),
    path("applications/", AdminApplicationListView.as_view(), name="onboarding-application-review-list"),
    path("applications/<str:application_id>/", AdminApplicationDetailView.as_view(), name="onboarding-application-review-detail"),
    path("applications/<str:application_id>/documents/<str:document_key>/", AdminDocumentView.as_view(), name="onboarding-application-review-document"),
    path("applications/<str:application_id>/approve/", AdminApproveApplicationView.as_view(), name="onboarding-application-review-approve"),
    path("applications/<str:application_id>/request-changes/", AdminRequestChangesView.as_view(), name="onboarding-application-review-request-changes"),
    path("applications/<str:application_id>/reject/", AdminRejectApplicationView.as_view(), name="onboarding-application-review-reject"),
]
