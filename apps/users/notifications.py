import logging
import requests
from django.conf import settings
from .models import DeviceToken

logger = logging.getLogger(__name__)

class PushNotificationService:
    @staticmethod
    def send_push(user, title, body, data=None):
        """
        Sends a push notification to all devices registered to a user.
        For now, this is a placeholder for Firebase Cloud Messaging (FCM).
        """
        tokens = list(DeviceToken.objects.filter(user=user).values_list("token", flat=True))
        
        if not tokens:
            logger.info(f"No device tokens found for user {user.username}. Skipping push.")
            return False

        logger.info(f"Sending Push to {user.username}: {title} - {body}")

        # Keep local/dev friction-free unless explicitly enabled.
        if not getattr(settings, "ENABLE_FCM_PUSH", False):
            logger.info("FCM push disabled by config (ENABLE_FCM_PUSH=False).")
            return True

        server_key = getattr(settings, "FCM_SERVER_KEY", "")
        if not server_key:
            logger.warning("ENABLE_FCM_PUSH=True but FCM_SERVER_KEY is empty. Skipping send.")
            return False

        url = "https://fcm.googleapis.com/fcm/send"
        headers = {
            "Authorization": f"key={server_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "registration_ids": tokens,
            "notification": {"title": title, "body": body},
            "data": data or {},
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=8)
            if response.status_code == 200:
                return True
            logger.warning("FCM send failed with status %s: %s", response.status_code, response.text)
            return False
        except requests.RequestException as exc:
            logger.exception("FCM request error: %s", exc)
            return False

    @classmethod
    def notify_new_order(cls, merchant_user, order_id):
        return cls.send_push(
            merchant_user, 
            "New Order Received! 🛍️", 
            f"You have a new order #{str(order_id)[:8]}. Open the app to accept it.",
            {"order_id": str(order_id), "type": "NEW_ORDER"}
        )

    @classmethod
    def notify_order_status(cls, customer_user, status, order_id):
        messages = {
            "ACCEPTED": "Your order has been accepted and is being prepared! 👨‍🍳",
            "READY": "Your order is ready for pickup! A rider is being assigned. 🛵",
            "ON_THE_WAY": "Your rider is on the way with your food! 🏁",
            "DELIVERED": "Enjoy your meal! Your order has been delivered. 😋",
            "CANCELLED": "We're sorry, your order has been cancelled. ❌"
        }
        msg = messages.get(status, f"Your order status is now {status}.")
        return cls.send_push(
            customer_user,
            "Order Update",
            msg,
            {"order_id": str(order_id), "type": "STATUS_UPDATE"}
        )

    @classmethod
    def notify_rider_delivery_offer(cls, rider_user, order):
        return cls.send_push(
            rider_user,
            "New delivery offer",
            f"Pickup from {order.store.name}. Open Sarig Rider to accept.",
            {"order_id": str(order.id), "type": "DELIVERY_OFFER"},
        )

    @classmethod
    def notify_rider_pickup_ready(cls, rider_user, order):
        return cls.send_push(
            rider_user,
            "Order ready for pickup",
            f"{order.store.name} is ready for pickup.",
            {"order_id": str(order.id), "type": "PICKUP_READY"},
        )

    @classmethod
    def notify_new_message(cls, recipient_user, sender_name, order_id):
        return cls.send_push(
            recipient_user,
            f"New message from {sender_name}",
            "Open the chat to see what they said.",
            {"order_id": str(order_id), "type": "NEW_CHAT_MESSAGE"}
        )
