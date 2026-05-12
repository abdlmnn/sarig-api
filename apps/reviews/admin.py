from django.contrib import admin
from .models import OrderReview

@admin.register(OrderReview)
class OrderReviewAdmin(admin.ModelAdmin):
    list_display = ('order_id_short', 'store', 'store_rating', 'rider_profile', 'rider_rating', 'created_at')
    list_filter = ('store_rating', 'rider_rating', 'created_at')
    search_fields = ('store__name', 'rider_profile__user__username', 'customer__username')
    readonly_fields = ('order', 'customer', 'store', 'rider_profile', 'created_at')

    def order_id_short(self, obj):
        return str(obj.order.id)[:8]
    order_id_short.short_description = "Order ID"
