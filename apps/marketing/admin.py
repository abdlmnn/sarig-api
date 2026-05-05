from django.contrib import admin
from .models import PromoCode

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'usage_count', 'usage_limit', 'is_active', 'expiry_date')
    list_filter = ('discount_type', 'is_active', 'expiry_date')
    search_fields = ('code',)
    readonly_fields = ('usage_count',)
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('code', 'description', 'is_active')
        }),
        ('Discount Logic', {
            'fields': ('discount_type', 'value', 'minimum_spend', 'max_discount_amount')
        }),
        ('Limits & Expiry', {
            'fields': ('usage_limit', 'usage_count', 'expiry_date')
        }),
    )
