import os
import requests
from django.conf import settings

class PayMongoService:
    BASE_URL = "https://api.paymongo.com/v1"

    @classmethod
    def get_headers(cls):
        # In a real app, use environment variables for API keys
        api_key = os.getenv("PAYMONGO_SECRET_KEY", "sk_test_placeholder")
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

        # In a real scenario, we'd make the actual request
        # response = requests.post(url, json=payload, headers=cls.get_headers())
        # return response.json()

        # Returning a mock response for now to keep development smooth
        return {
            "id": "cs_mock_123456789",
            "checkout_url": "https://checkout.paymongo.com/mock_session"
        }
