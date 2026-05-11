import json

from channels.generic.websocket import AsyncWebsocketConsumer


class RideConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return
        self.group_name = f"user_{user.id}_rides"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ride_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": event["event_type"],
                    "ride_id": event["ride_id"],
                    "status": event["status"],
                    "payload": event["payload"],
                }
            )
        )

