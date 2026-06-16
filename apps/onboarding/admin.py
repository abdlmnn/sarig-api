from django.contrib import admin
from .models import MerchantApplication, RiderApplication
from .services import ApplicationService


@admin.register(MerchantApplication)
class MerchantApplicationAdmin(admin.ModelAdmin):
    list_display = ("business_name", "business_type", "city", "applicant", "status", "created_at")
    list_filter = ("status", "business_type", "delivery_time", "city", "created_at")
    search_fields = ("business_name", "branch_name", "company_email", "contact_number", "applicant__username", "applicant__email")
    readonly_fields = ("id", "applicant", "created_at", "updated_at")
    fieldsets = (
        ("Application", {"fields": ("id", "applicant", "status", "admin_remarks")}),
        ("Business Info", {"fields": ("business_name", "branch_name", "business_type", "delivery_time")}),
        ("Owner Contact", {"fields": ("owner_first_name", "owner_last_name", "company_email", "contact_number")}),
        ("Business Address", {"fields": ("business_address", "street", "barangay", "city", "province", "postal_code")}),
        ("Map Pin", {"fields": ("pinned_address", "latitude", "longitude")}),
        ("Documents", {"fields": ("dti_sec_certificate", "mayors_permit", "bir_cor", "halal_certification", "owner_valid_id", "storefront_photo")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    actions = ["approve_selected", "reject_selected"]

    def approve_selected(self, request, queryset):
        for application in queryset:
            ApplicationService.approve_merchant(application)
        self.message_user(request, f"{queryset.count()} application(s) approved and stores created.")
    approve_selected.short_description = "Approve selected and create store"

    def reject_selected(self, request, queryset):
        queryset.update(status="REJECTED")
        self.message_user(request, f"{queryset.count()} application(s) rejected.")
    reject_selected.short_description = "Reject selected applications"


@admin.register(RiderApplication)
class RiderApplicationAdmin(admin.ModelAdmin):
    list_display = ("applicant", "vehicle_type", "plate_number", "status", "created_at")
    list_filter = ("status", "vehicle_type", "created_at")
    search_fields = ("applicant__username", "applicant__email", "plate_number")
    readonly_fields = ("id", "applicant", "created_at", "updated_at")
    actions = ["approve_selected", "reject_selected"]

    def approve_selected(self, request, queryset):
        for application in queryset:
            ApplicationService.approve_rider(application)
        self.message_user(request, f"{queryset.count()} rider(s) approved and role granted.")
    approve_selected.short_description = "Approve selected and grant Rider role"

    def reject_selected(self, request, queryset):
        queryset.update(status="REJECTED")
        self.message_user(request, f"{queryset.count()} rider application(s) rejected.")
    reject_selected.short_description = "Reject selected applications"
