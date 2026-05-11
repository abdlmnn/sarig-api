from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def publish_ride_event(ride, event_type: str, payload: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    message = {
        "type": "ride_event",
        "event_type": event_type,
        "ride_id": str(ride.id),
        "status": ride.status,
        "payload": payload,
    }

    # Passenger stream
    async_to_sync(channel_layer.group_send)(
        f"user_{ride.passenger_id}_rides",
        message,
    )

    # Rider stream (if assigned)
    if ride.rider_id:
        async_to_sync(channel_layer.group_send)(
            f"user_{ride.rider.user_id}_rides",
            message,
        )

