from django.contrib import admin

from .models import (
    AccountSetupToken,
    ApplicationEditToken,
    ApplicationStatusHistory,
    MerchantApplication,
    OnboardingNotificationDelivery,
    RiderApplication,
)
from .services import ApplicationService


@admin.register(MerchantApplication)
class MerchantApplicationAdmin(admin.ModelAdmin):
    list_display = ("application_id", "business_name", "business_type", "city", "status", "created_at")
    list_filter = ("status", "business_type", "delivery_time", "city", "created_at")
    search_fields = ("application_id", "business_name", "branch_name", "company_email", "contact_number")
    readonly_fields = ("id", "application_id", "applicant", "status", "created_at", "updated_at")
    actions = ["approve_selected", "reject_selected"]

    def approve_selected(self, request, queryset):
        for application in queryset:
            ApplicationService.approve_merchant(application, actor=request.user)
        self.message_user(request, f"{queryset.count()} application(s) approved.")

    approve_selected.short_description = "Approve selected merchant applications"

    def reject_selected(self, request, queryset):
        for application in queryset:
            ApplicationService.reject_application(application, "Rejected by admin action.", actor=request.user)
        self.message_user(request, f"{queryset.count()} application(s) rejected.")

    reject_selected.short_description = "Reject selected merchant applications"


@admin.register(RiderApplication)
class RiderApplicationAdmin(admin.ModelAdmin):
    list_display = ("application_id", "applicant_name", "vehicle_type", "plate_number", "status", "created_at")
    list_filter = ("status", "vehicle_type", "city", "created_at")
    search_fields = ("application_id", "first_name", "last_name", "email", "phone_number", "plate_number")
    readonly_fields = ("id", "application_id", "applicant", "status", "created_at", "updated_at")
    actions = ["approve_selected", "reject_selected"]

    def approve_selected(self, request, queryset):
        for application in queryset:
            ApplicationService.approve_rider(application, actor=request.user)
        self.message_user(request, f"{queryset.count()} rider application(s) approved.")

    approve_selected.short_description = "Approve selected rider applications"

    def reject_selected(self, request, queryset):
        for application in queryset:
            ApplicationService.reject_application(application, "Rejected by admin action.", actor=request.user)
        self.message_user(request, f"{queryset.count()} rider application(s) rejected.")

    reject_selected.short_description = "Reject selected rider applications"


@admin.register(ApplicationStatusHistory)
class ApplicationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("application_id", "application_type", "from_status", "to_status", "actor", "created_at")
    search_fields = ("application_id", "application_type")
    readonly_fields = ("id", "created_at")


@admin.register(ApplicationEditToken)
class ApplicationEditTokenAdmin(admin.ModelAdmin):
    list_display = ("application_id", "application_type", "expires_at", "revoked_at", "created_at")
    readonly_fields = ("id", "token", "created_at")


@admin.register(AccountSetupToken)
class AccountSetupTokenAdmin(admin.ModelAdmin):
    list_display = ("application_id", "application_type", "expires_at", "used_at", "revoked_at", "created_at")
    readonly_fields = ("id", "created_at")
    exclude = ("token",)


@admin.register(OnboardingNotificationDelivery)
class OnboardingNotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("application_id", "event", "channel", "status", "attempt_count", "sent_at", "created_at")
    list_filter = ("event", "channel", "status")
    search_fields = ("application_id", "recipient", "idempotency_key")
    readonly_fields = (
        "id",
        "event",
        "channel",
        "application_id",
        "application_type",
        "recipient",
        "template_key",
        "payload",
        "idempotency_key",
        "attempt_count",
        "last_error",
        "sent_at",
        "created_at",
        "updated_at",
    )
