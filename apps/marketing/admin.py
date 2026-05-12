from django.contrib import admin
from .models import PromoCode

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'usage_count', 'usage_limit', 'is_active', 'end_date')
    list_filter = ('discount_type', 'is_active', 'end_date')
    search_fields = ('code',)
    readonly_fields = ('usage_count',)
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('code', 'is_active')
        }),
        ('Discount Logic', {
            'fields': ('discount_type', 'discount_value', 'min_order_amount', 'max_discount_amount')
        }),
        ('Limits & Expiry', {
            'fields': ('usage_limit', 'usage_count', 'start_date', 'end_date')
        }),
    )
