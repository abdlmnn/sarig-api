import hashlib
import hmac
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.orders.models import Order, OrderStatus
from apps.payments.models import PaymentMethod, PaymentStatus, PaymentTransaction
from apps.users.models import User
from apps.vendors.models import BusinessVertical, Store


@override_settings(
    PAYMONGO_WEBHOOK_SECRET="test_webhook_secret",
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_STORE_EAGER_RESULT=False,
    CELERY_BROKER_URL="memory://",
    CELERY_RESULT_BACKEND="cache+memory://",
)
class PayMongoWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user("paycust", "paycust@test.com", "pw12345")
        self.merchant = User.objects.create_user("paymerch", "paymerch@test.com", "pw12345")
        vertical = BusinessVertical.objects.create(name="Restaurant", slug="restaurant-payments")
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Pay Store",
            latitude=7.1,
            longitude=125.4,
            street_address="Addr",
            city="Marawi",
        )

    def _create_order(self):
        return Order.objects.create(
            customer=self.customer,
            store=self.store,
            status=OrderStatus.PENDING,
            delivery_address_text="Addr",
            delivery_latitude=7.2,
            delivery_longitude=125.5,
            subtotal=Decimal("100"),
            delivery_fee=Decimal("40"),
            system_fee=Decimal("10"),
            total_amount=Decimal("150"),
        )

    def _create_transaction(self, order):
        return PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=PaymentMethod.PAYMONGO,
            status=PaymentStatus.PENDING,
            external_transaction_id=f"cs_test_{order.id}",
        )

    def _post_webhook(self, payload):
        import json

        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(
            b"test_webhook_secret",
            body,
            hashlib.sha256,
        ).hexdigest()
        return self.client.post(
            "/api/v1/payments/webhooks/paymongo/",
            body,
            content_type="application/json",
            HTTP_PAYMONGO_SIGNATURE=signature,
        )

    def _event_payload(self, event_type, checkout_session_id, payment_id=None):
        attributes = {
            "type": "checkout_session",
            "payments": [{"id": payment_id}] if payment_id else [],
            "metadata": {"order_id": ""},
        }
        return {
            "data": {
                "attributes": {
                    "type": event_type,
                    "data": {
                        "id": checkout_session_id,
                        "attributes": attributes,
                    },
                }
            }
        }

    @patch("apps.orders.tasks.auto_cancel_stale_order.apply_async")
    @patch("apps.users.notifications.PushNotificationService.notify_new_order")
    @patch("apps.catalog.services.InventoryService.deduct_stock_for_order")
    def test_paid_webhook_marks_transaction_success(self, stock_mock, notify_mock, cancel_mock):
        stock_mock.return_value = (True, "ok")
        order = self._create_order()
        tx = self._create_transaction(order)
        payload = self._event_payload(
            "checkout_session.payment.paid",
            tx.external_transaction_id,
            payment_id="pay_test_123",
        )

        res = self._post_webhook(payload)

        self.assertEqual(res.status_code, 200)
        tx.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(tx.status, PaymentStatus.SUCCESS)
        self.assertEqual(tx.payment_id, "pay_test_123")
        self.assertEqual(order.status, OrderStatus.PENDING)
        stock_mock.assert_called_once_with(order.id)
        notify_mock.assert_called_once()
        cancel_mock.assert_called_once()

    def test_failed_webhook_marks_transaction_failed_and_cancels_order(self):
        order = self._create_order()
        tx = self._create_transaction(order)
        payload = self._event_payload("checkout_session.payment.failed", tx.external_transaction_id)

        res = self._post_webhook(payload)

        self.assertEqual(res.status_code, 200)
        tx.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(tx.status, PaymentStatus.FAILED)
        self.assertEqual(order.status, OrderStatus.CANCELLED)

    def test_expired_webhook_marks_transaction_expired_and_cancels_order(self):
        order = self._create_order()
        tx = self._create_transaction(order)
        payload = self._event_payload("checkout_session.expired", tx.external_transaction_id)

        res = self._post_webhook(payload)

        self.assertEqual(res.status_code, 200)
        tx.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(tx.status, PaymentStatus.EXPIRED)
        self.assertEqual(order.status, OrderStatus.CANCELLED)

    def test_invalid_signature_is_rejected(self):
        response = self.client.post(
            "/api/v1/payments/webhooks/paymongo/",
            {"data": {}},
            format="json",
            HTTP_PAYMONGO_SIGNATURE="bad",
        )

        self.assertEqual(response.status_code, 403)
