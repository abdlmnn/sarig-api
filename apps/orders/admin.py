from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'unit_price', 'total_price')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'store', 'rider', 'status', 'delivery_method', 'total_amount', 'created_at')
    list_filter = ('status', 'delivery_method', 'created_at')
    search_fields = ('id', 'customer__username', 'store__name', 'rider__username')
    readonly_fields = ('id', 'customer', 'store', 'rider', 'total_amount', 'created_at', 'updated_at')
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Info', {
            'fields': ('id', 'status', 'delivery_method', 'total_amount', 'created_at')
        }),
        ('Parties', {
            'fields': ('customer', 'store', 'rider')
        }),
        ('Logistics', {
            'fields': ('delivery_address_text', 'delivery_latitude', 'delivery_longitude', 'estimated_arrival_time')
        }),
        ('Finance', {
            'fields': ('promo_code', 'discount_amount', 'delivery_fee', 'system_fee')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'store', 'rider')
