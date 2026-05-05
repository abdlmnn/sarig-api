from django.contrib import admin
from .models import PaymentTransaction

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id_short", "order_link", "payment_method", "status", "amount", "created_at")
    list_filter = ("payment_method", "status", "created_at")
    search_fields = ("id", "external_transaction_id", "order__id")
    readonly_fields = ("provider_raw_response", "created_at", "updated_at")

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "TX ID"

    def order_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        url = reverse("admin:orders_order_change", args=[obj.order.id])
        return format_html('<a href="{}">Order #{}</a>', url, str(obj.order.id)[:8])
    order_link.short_description = "Order"
