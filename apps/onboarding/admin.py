from django.contrib import admin
from .models import MerchantApplication, RiderApplication
from .services import ApplicationService


@admin.register(MerchantApplication)
class MerchantApplicationAdmin(admin.ModelAdmin):
    list_display = ("business_name", "applicant", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("business_name", "applicant__username", "applicant__email")
    readonly_fields = ("id", "applicant", "created_at", "updated_at")
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
