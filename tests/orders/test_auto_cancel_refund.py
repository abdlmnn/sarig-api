from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.orders.models import Order, OrderStatus
from apps.orders.tasks import auto_cancel_stale_order
from apps.payments.models import PaymentMethod, PaymentStatus, PaymentTransaction
from apps.users.models import User
from apps.vendors.models import BusinessVertical, Store


class AutoCancelRefundTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user("cust2", "cust2@test.com", "pw12345")
        self.merchant = User.objects.create_user("merch2", "merch2@test.com", "pw12345")
        vertical = BusinessVertical.objects.create(name="Restaurant", slug="restaurant-ac")
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Store 2",
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

    @patch("apps.users.notifications.PushNotificationService.notify_order_status")
    @patch("apps.payments.services.PayMongoService.create_refund")
    def test_auto_cancel_stale_order_attempts_refund(self, refund_mock, notify_mock):
        refund_mock.return_value = {"status": "success"}
        order = self._create_order()
        tx = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=PaymentMethod.PAYMONGO,
            status=PaymentStatus.SUCCESS,
            payment_id="pay_auto_1",
        )

        auto_cancel_stale_order(str(order.id))

        order.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(tx.status, PaymentStatus.REFUNDED)
        refund_mock.assert_called_once()
        notify_mock.assert_called_once()
