import json
from unittest.mock import AsyncMock

from channels.layers import InMemoryChannelLayer
from django.test import SimpleTestCase

from apps.common.consumers import RealtimeConsumer
from apps.common.realtime import REALTIME_GROUP


class RealtimeConsumerTest(SimpleTestCase):
    async def test_realtime_event_sends_serialized_payload(self):
        consumer = RealtimeConsumer()
        consumer.send = AsyncMock()

        await consumer.realtime_event(
            {
                "type": "realtime.event",
                "kind": "order_updated",
                "payload": {"order_id": "x"},
            }
        )

        consumer.send.assert_awaited_once()
        frame = json.loads(consumer.send.await_args.kwargs["text_data"])
        self.assertEqual(frame, {"kind": "order_updated", "payload": {"order_id": "x"}})

    async def test_connect_and_disconnect_join_and_leave_group(self):
        layer = InMemoryChannelLayer()
        consumer = RealtimeConsumer()
        consumer.channel_layer = layer
        consumer.channel_name = "test_realtime_channel"
        consumer.accept = AsyncMock()

        await consumer.connect()
        consumer.accept.assert_awaited_once()
        self.assertIn(
            "test_realtime_channel",
            layer.groups.get(REALTIME_GROUP, {}),
        )

        await consumer.disconnect(None)
        self.assertNotIn(
            "test_realtime_channel",
            layer.groups.get(REALTIME_GROUP, {}),
        )
