from django.contrib import admin

from .models import AdminAlert, ServiceZone, ServiceZoneAssignment, ServiceZoneMetricSnapshot


@admin.register(ServiceZone)
class ServiceZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "province", "is_active", "priority", "updated_at")
    list_filter = ("city", "province", "is_active")
    search_fields = ("name", "slug", "city", "province")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ServiceZoneMetricSnapshot)
class ServiceZoneMetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ("zone", "load_status", "active_orders", "available_riders", "average_delay_minutes", "created_at")
    list_filter = ("load_status", "created_at")
    search_fields = ("zone__name",)
    readonly_fields = ("created_at",)


@admin.register(ServiceZoneAssignment)
class ServiceZoneAssignmentAdmin(admin.ModelAdmin):
    list_display = ("zone", "entity_type", "entity_id", "source", "created_at")
    list_filter = ("entity_type", "source")
    search_fields = ("zone__name", "entity_id")


@admin.register(AdminAlert)
class AdminAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "severity", "source", "is_resolved", "created_at", "resolved_at")
    list_filter = ("severity", "source", "is_resolved")
    search_fields = ("title", "message", "source")
