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
        tokens = DeviceToken.objects.filter(user=user).values_list('token', flat=True)
        
        if not tokens:
            logger.info(f"No device tokens found for user {user.username}. Skipping push.")
            return False

        logger.info(f"Sending Push to {user.username}: {title} - {body}")
        
        # In a real-world scenario with FCM:
        # url = "https://fcm.googleapis.com/fcm/send"
        # headers = {
        #     "Authorization": f"key={settings.FCM_SERVER_KEY}",
        #     "Content-Type": "application/json"
        # }
        # payload = {
        #     "registration_ids": list(tokens),
        #     "notification": {"title": title, "body": body},
        #     "data": data or {}
        # }
        # response = requests.post(url, json=payload, headers=headers)
        # return response.status_code == 200

        # Mock success for simulation
        return True

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
    def notify_new_message(cls, recipient_user, sender_name, order_id):
        return cls.send_push(
            recipient_user,
            f"New message from {sender_name}",
            "Open the chat to see what they said.",
            {"order_id": str(order_id), "type": "NEW_CHAT_MESSAGE"}
        )
