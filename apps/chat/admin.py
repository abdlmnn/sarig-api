from django.contrib import admin
from .models import ChatMessage

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('order_short_id', 'sender', 'content_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('order__id', 'sender__username', 'content')
    readonly_fields = ('order', 'sender', 'content', 'created_at')

    def order_short_id(self, obj):
        return str(obj.order.id)[:8]
    order_short_id.short_description = "Order ID"

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Message"
