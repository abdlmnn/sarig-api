import hashlib
import hmac
import json
from decimal import Decimal
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.users.models import User
from apps.vendors.models import Store, BusinessVertical
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentStatus


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_STORE_EAGER_RESULT=False,
    CELERY_BROKER_URL="memory://",
    CELERY_RESULT_BACKEND="cache+memory://",
)
class PayMongoWebhookSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        merchant = User.objects.create_user(username="m1", email="m1@test.com", password="pw12345")
        customer = User.objects.create_user(username="c1", email="c1@test.com", password="pw12345")
        vertical = BusinessVertical.objects.create(name="Restaurant", slug="restaurant")
        store = Store.objects.create(
            owner=merchant,
            vertical=vertical,
            name="Store",
            latitude=7.1,
            longitude=125.4,
            street_address="Addr",
            city="Marawi",
        )
        order = Order.objects.create(
            customer=customer,
            store=store,
            delivery_address_text="Addr",
            delivery_latitude=7.2,
            delivery_longitude=125.5,
            subtotal=Decimal("100"),
            delivery_fee=Decimal("40"),
            system_fee=Decimal("10"),
            total_amount=Decimal("150"),
        )
        self.tx = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=PaymentMethod.PAYMONGO,
            status=PaymentStatus.PENDING,
            external_transaction_id="cs_mock_123",
        )

    @override_settings(PAYMONGO_WEBHOOK_SECRET="topsecret")
    def test_webhook_rejects_missing_signature_when_secret_is_set(self):
        payload = {
            "data": {
                "attributes": {
                    "type": "checkout_session.payment.paid",
                    "data": {"id": "cs_mock_123", "attributes": {"payment_id": "pay_1"}},
                }
            }
        }
        res = self.client.post("/api/v1/payments/webhooks/paymongo/", payload, format="json")
        self.assertEqual(res.status_code, 403)

    @override_settings(PAYMONGO_WEBHOOK_SECRET="topsecret")
    def test_webhook_accepts_valid_signature(self):
        payload = {
            "data": {
                "attributes": {
                    "type": "checkout_session.payment.paid",
                    "data": {"id": "cs_mock_123", "attributes": {"payment_id": "pay_1"}},
                }
            }
        }
        raw = json.dumps(payload).encode("utf-8")
        signature = hmac.new(b"topsecret", raw, hashlib.sha256).hexdigest()
        res = self.client.post(
            "/api/v1/payments/webhooks/paymongo/",
            data=raw,
            content_type="application/json",
            HTTP_PAYMONGO_SIGNATURE=signature,
        )
        self.assertEqual(res.status_code, 200)

    @override_settings(PAYMONGO_WEBHOOK_SECRET="topsecret")
    def test_webhook_is_idempotent_for_success_status(self):
        payload = {
            "data": {
                "attributes": {
                    "type": "checkout_session.payment.paid",
                    "data": {"id": "cs_mock_123", "attributes": {"payment_id": "pay_1"}},
                }
            }
        }
        raw = json.dumps(payload).encode("utf-8")
        signature = hmac.new(b"topsecret", raw, hashlib.sha256).hexdigest()

        first = self.client.post(
            "/api/v1/payments/webhooks/paymongo/",
            data=raw,
            content_type="application/json",
            HTTP_PAYMONGO_SIGNATURE=signature,
        )
        second = self.client.post(
            "/api/v1/payments/webhooks/paymongo/",
            data=raw,
            content_type="application/json",
            HTTP_PAYMONGO_SIGNATURE=signature,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, PaymentStatus.SUCCESS)
