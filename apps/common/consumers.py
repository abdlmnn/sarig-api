import json

from channels.generic.websocket import AsyncWebsocketConsumer

from apps.common.realtime import REALTIME_GROUP


class RealtimeConsumer(AsyncWebsocketConsumer):
    """Public realtime event stream. Clients may connect without credentials."""

    async def connect(self):
        self.group_name = REALTIME_GROUP
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def realtime_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "kind": event["kind"],
                    "payload": event.get("payload", {}),
                }
            )
        )
