import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        self.room_group_name = f"chat_{self.order_id}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # Verify access
        if not await self.check_order_access():
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_content = data.get("message")

        if not message_content:
            return

        # Save message to DB
        saved_msg = await self.save_message(message_content)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message_content,
                "sender": self.user.username,
                "timestamp": str(saved_msg.created_at)
            }
        )

        # Notify Recipient (Push Notification)
        await self.notify_recipient_push(message_content)

    async def notify_recipient_push(self, message):
        from apps.orders.models import Order
        from apps.users.notifications import PushNotificationService
        
        # We need to run this in a thread-safe way for Django models
        order = await database_sync_to_async(Order.objects.get)(id=self.order_id)
        
        # Determine who is the recipient
        recipient = order.customer if self.user == order.rider else order.rider
        
        # Trigger the push
        if recipient:
            # We don't need to await this as it's a simple function call in our mock
            PushNotificationService.notify_new_message(recipient, self.user.username, order.id)

    # Receive message from room group
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "type": "CHAT_MESSAGE",
            "message": event["message"],
            "sender": event["sender"],
            "timestamp": event["timestamp"]
        }))

    @database_sync_to_async
    def check_order_access(self):
        from apps.orders.models import Order, OrderStatus
        try:
            order = Order.objects.get(id=self.order_id)
            
            # 1. Ownership Check: Only Customer or Assigned Rider can chat
            if self.user != order.customer and self.user != order.rider:
                return False
            
            # 2. Lifecycle Check: Chat is only open for active orders
            if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
                return False
                
            return True
        except ObjectDoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        from .models import ChatMessage
        from apps.orders.models import Order
        order = Order.objects.get(id=self.order_id)
        return ChatMessage.objects.create(
            order=order,
            sender=self.user,
            content=content
        )
