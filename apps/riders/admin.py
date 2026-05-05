from django.contrib import admin
from .models import RiderProfile, RiderTransaction

class RiderTransactionInline(admin.TabularInline):
    model = RiderTransaction
    extra = 0
    readonly_fields = ('order', 'amount', 'transaction_type', 'created_at')

@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'is_online', 'is_available', 'can_do_delivery', 'can_do_ride_hailing')
    list_filter = ('is_online', 'is_available', 'can_do_delivery', 'can_do_ride_hailing')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('balance',)
    inlines = [RiderTransactionInline]

@admin.register(RiderTransaction)
class RiderTransactionAdmin(admin.ModelAdmin):
    list_display = ('rider_profile', 'amount', 'transaction_type', 'order', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('rider_profile__user__username', 'order__id')
