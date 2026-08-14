import os
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class PayMongoService:
    BASE_URL = "https://api.paymongo.com/v1"
    SUPPORTED_PAYMENT_METHODS = {
        "GCASH": "gcash",
        "MAYA": "paymaya",
        "CARD": "card",
    }

    @staticmethod
    def _is_production_settings():
        return str(getattr(settings, "SETTINGS_MODULE", "")).endswith(".prod")

    @classmethod
    def get_headers(cls):
        api_key = getattr(settings, "PAYMONGO_SECRET_KEY", "") or os.getenv(
            "PAYMONGO_SECRET_KEY", ""
        )
        if not api_key:
            raise ImproperlyConfigured(
                "PAYMONGO_SECRET_KEY is required for PayMongo API calls."
            )
        import base64

        auth = base64.b64encode(f"{api_key}:".encode()).decode()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        }

    @staticmethod
    def _to_centavos(amount):
        return int(Decimal(str(amount)) * 100)

    @classmethod
    def get_enabled_payment_methods(cls):
        configured = getattr(settings, "PAYMONGO_ENABLED_PAYMENT_METHODS", "")
        configured_methods = cls._normalize_configured_payment_methods(configured)

        if configured_methods:
            return configured_methods

        if getattr(settings, "PAYMONGO_USE_MOCK", settings.DEBUG):
            if cls._is_production_settings():
                raise ImproperlyConfigured(
                    "PAYMONGO_USE_MOCK cannot be enabled in production."
                )
            return list(cls.SUPPORTED_PAYMENT_METHODS)

        url = f"{cls.BASE_URL}/merchants/capabilities/payment_methods"
        response = requests.get(url, headers=cls.get_headers(), timeout=15)
        response.raise_for_status()
        active_methods = cls._extract_capability_methods(response.json())
        return active_methods

    @classmethod
    def get_enabled_paymongo_method_types(cls):
        method_types = [
            cls.SUPPORTED_PAYMENT_METHODS[method]
            for method in cls.get_enabled_payment_methods()
        ]
        if not method_types:
            raise ImproperlyConfigured(
                "At least one PayMongo payment method must be enabled."
            )
        return method_types

    @classmethod
    def _normalize_configured_payment_methods(cls, value):
        methods = []
        aliases = {
            "PAYMAYA": "MAYA",
            "MAYA": "MAYA",
            "GCASH": "GCASH",
            "CARD": "CARD",
        }
        for method in str(value or "").split(","):
            normalized = aliases.get(method.strip().upper())
            if normalized and normalized in cls.SUPPORTED_PAYMENT_METHODS:
                methods.append(normalized)
        return list(dict.fromkeys(methods))

    @classmethod
    def _extract_capability_methods(cls, payload):
        data = payload
        if isinstance(payload, dict):
            data = payload.get("data", payload)
        if isinstance(data, dict):
            data = data.get("attributes", {}).get("payment_methods", [])

        active = []
        aliases = {
            "gcash": "GCASH",
            "paymaya": "MAYA",
            "maya": "MAYA",
            "card": "CARD",
        }
        for method in data if isinstance(data, list) else []:
            if isinstance(method, dict):
                method = method.get("id") or method.get("type") or method.get("name")
            normalized = aliases.get(str(method).strip().lower())
            if normalized and normalized in cls.SUPPORTED_PAYMENT_METHODS:
                active.append(normalized)
        return list(dict.fromkeys(active))

    @classmethod
    def create_checkout_session(
        cls, amount, description, order_id, success_url=None, cancel_url=None
    ):
        url = f"{cls.BASE_URL}/checkout_sessions"
        success_url = success_url or getattr(settings, "PAYMONGO_SUCCESS_URL", "")
        cancel_url = cancel_url or getattr(settings, "PAYMONGO_CANCEL_URL", "")

        payload = {
            "data": {
                "attributes": {
                    "line_items": [
                        {
                            "amount": cls._to_centavos(amount),
                            "currency": "PHP",
                            "description": description,
                            "name": "Order Payment",
                            "quantity": 1,
                        }
                    ],
                    "payment_method_types": cls.get_enabled_paymongo_method_types(),
                    "description": description,
                    "metadata": {
                        "order_id": str(order_id),
                        "platform": "sarig",
                    },
                }
            }
        }
        if success_url:
            payload["data"]["attributes"]["success_url"] = cls._with_order_query(
                success_url,
                order_id,
            )
        if cancel_url:
            payload["data"]["attributes"]["cancel_url"] = cls._with_order_query(
                cancel_url,
                order_id,
            )

        if getattr(settings, "PAYMONGO_USE_MOCK", settings.DEBUG):
            if cls._is_production_settings():
                raise ImproperlyConfigured(
                    "PAYMONGO_USE_MOCK cannot be enabled in production."
                )
            return {
                "id": f"cs_mock_{order_id}",
                "checkout_url": "https://checkout.paymongo.com/mock_session",
                "raw": payload["data"],
            }

        response = requests.post(
            url, json=payload, headers=cls.get_headers(), timeout=15
        )
        response.raise_for_status()
        data = response.json()["data"]
        attributes = data.get("attributes", {})
        return {
            "id": data["id"],
            "checkout_url": attributes.get("checkout_url")
            or attributes.get("payments", [{}])[0].get("checkout_url"),
            "raw": data,
        }

    @staticmethod
    def _with_order_query(url, order_id):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["order_id"] = str(order_id)
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

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
                    "amount": cls._to_centavos(amount),
                    "payment_id": payment_id,
                    "reason": reason,
                    "notes": "Order rejected by merchant",
                }
            }
        }

        if getattr(settings, "PAYMONGO_USE_MOCK", settings.DEBUG):
            if cls._is_production_settings():
                raise ImproperlyConfigured(
                    "PAYMONGO_USE_MOCK cannot be enabled in production."
                )
            return {"status": "success", "refund_id": "ref_mock_123"}

        response = requests.post(
            url, json=payload, headers=cls.get_headers(), timeout=15
        )
        response.raise_for_status()
        return response.json()
