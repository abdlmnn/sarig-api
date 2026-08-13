import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from apps.orders.models import Order
from apps.vendors.models import Store


@database_sync_to_async
def _can_access_store_orders(user, store_id):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return Store.objects.filter(id=store_id).exists()
    return Store.objects.filter(id=store_id, owner=user).exists()


@database_sync_to_async
def _can_access_order(user, order_id):
    if not user or not user.is_authenticated:
        return False
    queryset = Order.objects.select_related("store", "customer", "rider")
    try:
        order = queryset.get(id=order_id)
    except Order.DoesNotExist:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return (
        order.customer_id == user.id
        or order.rider_id == user.id
        or order.store.owner_id == user.id
    )

class MerchantOrderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.store_id = self.scope["url_route"]["kwargs"]["store_id"]
        self.store_group_name = f"store_{self.store_id}_orders"

        if not await _can_access_store_orders(self.scope.get("user"), self.store_id):
            await self.close(code=4403)
            return

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

        if not await _can_access_order(self.scope.get("user"), self.order_id):
            await self.close(code=4403)
            return

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


class RiderOfferConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not await self._is_rider(user):
            await self.close(code=4403)
            return

        self.rider_group_name = f"rider_{user.id}"
        await self.channel_layer.group_add(self.rider_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "rider_group_name"):
            await self.channel_layer.group_discard(self.rider_group_name, self.channel_name)

    async def delivery_offer(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def _is_rider(self, user):
        return user.roles.filter(name="Rider").exists()
