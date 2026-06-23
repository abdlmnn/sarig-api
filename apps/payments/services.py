import os
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

class PayMongoService:
    BASE_URL = "https://api.paymongo.com/v1"

    @staticmethod
    def _is_production_settings():
        return str(getattr(settings, "SETTINGS_MODULE", "")).endswith(".prod")

    @classmethod
    def get_headers(cls):
        api_key = getattr(settings, "PAYMONGO_SECRET_KEY", "") or os.getenv("PAYMONGO_SECRET_KEY", "")
        if not api_key:
            raise ImproperlyConfigured("PAYMONGO_SECRET_KEY is required for PayMongo API calls.")
        import base64
        auth = base64.b64encode(f"{api_key}:".encode()).decode()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}"
        }

    @classmethod
    def create_checkout_session(cls, amount, description, success_url=None, cancel_url=None):
        """
        Creates a checkout session in PayMongo.
        Amount should be in centavos (PHP * 100).
        """
        url = f"{cls.BASE_URL}/checkout_sessions"

        payload = {
            "data": {
                "attributes": {
                    "billing": {
                        # Add default billing info if needed
                    },
                    "line_items": [
                        {
                            "amount": int(amount * 100),
                            "currency": "PHP",
                            "description": description,
                            "name": "Order Payment",
                            "quantity": 1
                        }
                    ],
                    "payment_method_types": ["gcash", "paymaya", "card"],
                    "description": description
                }
            }
        }

        if getattr(settings, "PAYMONGO_USE_MOCK", settings.DEBUG):
            if cls._is_production_settings():
                raise ImproperlyConfigured("PAYMONGO_USE_MOCK cannot be enabled in production.")
            return {
                "id": "cs_mock_123456789",
                "checkout_url": "https://checkout.paymongo.com/mock_session"
            }

        response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=15)
        response.raise_for_status()
        data = response.json()["data"]
        attributes = data.get("attributes", {})
        return {
            "id": data["id"],
            "checkout_url": attributes.get("checkout_url") or attributes.get("payments", [{}])[0].get("checkout_url"),
            "raw": data,
        }

    @classmethod
    def create_refund(cls, payment_id, amount, reason="requested_by_customer"):
        """
        Refunds a specific payment in PayMongo.
        Amount is in decimal PHP (e.g. 150.00).
        """
        url = f"{cls.BASE_URL}/refunds"
        
        payload = {
            "data": {
                "attributes": {
                    "amount": int(amount * 100),
                    "payment_id": payment_id,
                    "reason": reason,
                    "notes": "Order rejected by merchant"
                }
            }
        }

        if getattr(settings, "PAYMONGO_USE_MOCK", settings.DEBUG):
            if cls._is_production_settings():
                raise ImproperlyConfigured("PAYMONGO_USE_MOCK cannot be enabled in production.")
            return {"status": "success", "refund_id": "ref_mock_123"}

        response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=15)
        response.raise_for_status()
        return response.json()
