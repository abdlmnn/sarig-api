import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

REALTIME_GROUP = "realtime_broadcast"


def broadcast_realtime_event(kind, payload):
    """Broadcast a lightweight realtime event to every connected client."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            REALTIME_GROUP,
            {
                "type": "realtime.event",
                "kind": kind,
                "payload": payload,
            },
        )
    except Exception as exc:
        logger.warning("Failed to broadcast realtime event %s: %s", kind, exc)
