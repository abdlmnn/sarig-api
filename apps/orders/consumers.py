import json
from channels.generic.websocket import AsyncWebsocketConsumer

class MerchantOrderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.store_id = self.scope["url_route"]["kwargs"]["store_id"]
        self.store_group_name = f"store_{self.store_id}_orders"

        # Join store group
        await self.channel_layer.group_add(
            self.store_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave store group
        await self.channel_layer.group_discard(
            self.store_group_name,
            self.channel_name
        )

    # Receive message from room group
    async def order_alert(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "type": "NEW_ORDER",
            "data": message
        }))


class OrderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        self.order_group_name = f"order_{self.order_id}"

        # Join order group
        await self.channel_layer.group_add(
            self.order_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave order group
        await self.channel_layer.group_discard(
            self.order_group_name,
            self.channel_name
        )

    # Receive status updates
    async def status_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "STATUS_UPDATE",
            "status": event["status"]
        }))

    # Receive location updates from rider
    async def location_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "LOCATION_UPDATE",
            "latitude": event["latitude"],
            "longitude": event["longitude"],
            "remaining_minutes": event.get("remaining_minutes"),
            "distance_km": event.get("distance_km")
        }))
