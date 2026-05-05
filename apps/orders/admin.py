from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("unit_price",)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id_short", "customer", "store", "status", "total_amount", "created_at")
    list_filter = ("status", "created_at", "store")
    search_fields = ("id", "customer__username", "store__name")
    inlines = [OrderItemInline]
    readonly_fields = ("created_at", "updated_at")

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "Order ID"
