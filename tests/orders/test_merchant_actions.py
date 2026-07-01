from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.users.models import User
from apps.vendors.models import Store, BusinessVertical
from apps.orders.models import Order, OrderStatus
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentStatus


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_STORE_EAGER_RESULT=False,
    CELERY_BROKER_URL="memory://",
    CELERY_RESULT_BACKEND="cache+memory://",
)
class MerchantOrderActionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user("cust", "cust@test.com", "pw12345")
        self.merchant = User.objects.create_user("merch", "merch@test.com", "pw12345")
        vertical, _ = BusinessVertical.objects.get_or_create(
            slug="restaurant",
            defaults={"name": "Restaurant"},
        )
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Store",
            latitude=7.1,
            longitude=125.4,
            street_address="Addr",
            city="Marawi",
        )

    def _create_order(self, status=OrderStatus.PENDING, delivery_method="DELIVERY"):
        return Order.objects.create(
            customer=self.customer,
            store=self.store,
            delivery_method=delivery_method,
            status=status,
            delivery_address_text="Addr",
            delivery_latitude=7.2,
            delivery_longitude=125.5,
            subtotal=Decimal("100"),
            delivery_fee=Decimal("40"),
            system_fee=Decimal("10"),
            total_amount=Decimal("150"),
        )

    def test_accept_moves_order_to_accepted(self):
        order = self._create_order(status=OrderStatus.PENDING)
        self.client.force_authenticate(user=self.merchant)
        res = self.client.post(f"/api/v1/orders/{order.id}/action/", {"action": "accept"}, format="json")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.ACCEPTED)

    @patch("apps.riders.services.RiderDispatcherService.assign_rider_to_order")
    def test_mark_ready_dispatches_for_delivery(self, assign_mock):
        order = self._create_order(status=OrderStatus.ACCEPTED, delivery_method="DELIVERY")
        self.client.force_authenticate(user=self.merchant)
        res = self.client.post(f"/api/v1/orders/{order.id}/action/", {"action": "mark_ready"}, format="json")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.READY)
        assign_mock.assert_called_once()

    @patch("apps.payments.services.PayMongoService.create_refund")
    def test_reject_paid_order_marks_refunded(self, refund_mock):
        refund_mock.return_value = {"status": "success"}
        order = self._create_order(status=OrderStatus.ACCEPTED, delivery_method="DELIVERY")
        tx = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=PaymentMethod.PAYMONGO,
            status=PaymentStatus.SUCCESS,
            payment_id="pay_123",
        )
        self.client.force_authenticate(user=self.merchant)
        res = self.client.post(f"/api/v1/orders/{order.id}/action/", {"action": "reject"}, format="json")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(tx.status, PaymentStatus.REFUNDED)
        refund_mock.assert_called_once()
