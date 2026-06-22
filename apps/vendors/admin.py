from django.contrib import admin
from .models import BusinessVertical, Store


@admin.register(BusinessVertical)
class BusinessVerticalAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "is_active")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "branch_name",
        "owner",
        "vertical",
        "city",
        "is_open",
        "is_active",
    )

    list_filter = (
        "vertical",
        "delivery_time",
        "city",
        "province",
        "is_open",
        "is_active",
    )

    search_fields = (
        "name",
        "branch_name",
        "company_email",
        "contact_number",
        "city",
        "barangay",
        "province",
        "owner__username",
    )

    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Info", {"fields": ("owner", "vertical", "name", "branch_name", "company_email", "contact_number", "delivery_time")}),
        # LOCATION (HYBRID MODE)
        (
            "Location (Temporary)",
            {"fields": ("latitude", "longitude", "street_address", "pinned_address", "city", "barangay", "province", "postal_code")},
        ),
        # ("Location (GeoDjango)", {
        #     "fields": ("location", "street_address", "city")
        # }),
        ("Business Settings", {"fields": ("commission_rate", "is_open", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
