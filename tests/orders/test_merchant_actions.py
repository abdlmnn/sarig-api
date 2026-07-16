from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.users.models import Role, User
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
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        self.merchant.roles.add(merchant_role)
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

    def test_mark_preparing_moves_accepted_order_to_preparing(self):
        order = self._create_order(status=OrderStatus.ACCEPTED)
        self.client.force_authenticate(user=self.merchant)
        res = self.client.post(f"/api/v1/orders/{order.id}/action/", {"action": "mark_preparing"}, format="json")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PREPARING)

    def test_mark_preparing_rejects_pending_order(self):
        order = self._create_order(status=OrderStatus.PENDING)
        self.client.force_authenticate(user=self.merchant)
        res = self.client.post(f"/api/v1/orders/{order.id}/action/", {"action": "mark_preparing"}, format="json")
        self.assertEqual(res.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PENDING)
    @patch("apps.riders.services.RiderDispatcherService.assign_rider_to_order")
    def test_mark_ready_dispatches_for_delivery(self, assign_mock):
        order = self._create_order(status=OrderStatus.ACCEPTED, delivery_method="DELIVERY")
        self.client.force_authenticate(user=self.merchant)
        res = self.client.post(f"/api/v1/orders/{order.id}/action/", {"action": "mark_ready"}, format="json")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.READY)
        assign_mock.assert_called_once()

    @patch("apps.riders.services.RiderDispatcherService.assign_rider_to_order")
    def test_mark_ready_accepts_preparing_order(self, assign_mock):
        order = self._create_order(status=OrderStatus.PREPARING, delivery_method="DELIVERY")
        self.client.force_authenticate(user=self.merchant)
        res = self.client.post(f"/api/v1/orders/{order.id}/action/", {"action": "mark_ready"}, format="json")
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.READY)
        assign_mock.assert_called_once()

    def test_other_merchant_cannot_manage_order(self):
        other_merchant = User.objects.create_user("other", "other@test.com", "pw12345")
        order = self._create_order(status=OrderStatus.PENDING)
        self.client.force_authenticate(user=other_merchant)
        res = self.client.post(f"/api/v1/orders/{order.id}/action/", {"action": "accept"}, format="json")
        self.assertEqual(res.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PENDING)

    def test_merchant_can_view_owned_order_detail(self):
        order = self._create_order(status=OrderStatus.ACCEPTED)
        payment = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=PaymentMethod.PAYMONGO,
            status=PaymentStatus.SUCCESS,
            external_transaction_id="mock_detail_payment",
            provider_raw_response={"private": "provider-data"},
        )
        self.client.force_authenticate(user=self.merchant)
        res = self.client.get(f"/api/v1/orders/{order.id}/merchant-detail/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["id"], str(order.id))
        self.assertEqual(res.data["delivery_method"], order.delivery_method)
        self.assertEqual(res.data["tracking"]["customer"]["latitude"], "7.200000")
        self.assertEqual(res.data["tracking"]["store"]["longitude"], "125.400000")
        self.assertEqual(res.data["payment"]["id"], str(payment.id))
        self.assertEqual(res.data["payment"]["method"], PaymentMethod.PAYMONGO)
        self.assertEqual(res.data["payment"]["status"], PaymentStatus.SUCCESS)
        self.assertEqual(res.data["payment"]["amount"], "150.00")
        self.assertNotIn("provider_raw_response", res.data["payment"])

    def test_merchant_order_list_returns_owned_active_orders(self):
        active_order = self._create_order(status=OrderStatus.ACCEPTED)
        self._create_order(status=OrderStatus.CANCELLED)
        self.client.force_authenticate(user=self.merchant)
        res = self.client.get("/api/v1/orders/merchant/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["orders"]), 1)
        self.assertEqual(res.data["orders"][0]["order_id"], str(active_order.id))

    def test_merchant_order_list_supports_status_filter(self):
        self._create_order(status=OrderStatus.ACCEPTED)
        ready_order = self._create_order(status=OrderStatus.READY)
        self.client.force_authenticate(user=self.merchant)
        res = self.client.get("/api/v1/orders/merchant/", {"status": "READY"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["orders"]), 1)
        self.assertEqual(res.data["orders"][0]["order_id"], str(ready_order.id))

    def test_merchant_order_list_returns_oldest_first(self):
        newer_order = self._create_order(status=OrderStatus.PENDING)
        older_order = self._create_order(status=OrderStatus.PENDING)
        Order.objects.filter(id=older_order.id).update(
            created_at=timezone.now() - timedelta(minutes=15)
        )
        Order.objects.filter(id=newer_order.id).update(
            created_at=timezone.now() - timedelta(minutes=3)
        )

        self.client.force_authenticate(user=self.merchant)
        res = self.client.get("/api/v1/orders/merchant/", {"status": "ACTIVE"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["orders"][0]["order_id"], str(older_order.id))
        self.assertEqual(res.data["orders"][1]["order_id"], str(newer_order.id))

    def test_merchant_all_order_list_returns_oldest_first(self):
        newer_order = self._create_order(status=OrderStatus.DELIVERED)
        older_order = self._create_order(status=OrderStatus.CANCELLED)
        Order.objects.filter(id=older_order.id).update(
            created_at=timezone.now() - timedelta(minutes=15)
        )
        Order.objects.filter(id=newer_order.id).update(
            created_at=timezone.now() - timedelta(minutes=3)
        )

        self.client.force_authenticate(user=self.merchant)
        res = self.client.get("/api/v1/orders/merchant/", {"status": "ALL"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["orders"][0]["order_id"], str(older_order.id))
        self.assertEqual(res.data["orders"][1]["order_id"], str(newer_order.id))

    def test_other_merchant_cannot_view_order_detail(self):
        other_merchant = User.objects.create_user("viewer", "viewer@test.com", "pw12345")
        other_merchant.roles.add(Role.objects.get(name="Merchant"))
        order = self._create_order(status=OrderStatus.ACCEPTED)
        self.client.force_authenticate(user=other_merchant)
        res = self.client.get(f"/api/v1/orders/{order.id}/merchant-detail/")
        self.assertEqual(res.status_code, 404)

    def test_reject_requires_reason(self):
        order = self._create_order(status=OrderStatus.ACCEPTED)
        self.client.force_authenticate(user=self.merchant)
        res = self.client.post(
            f"/api/v1/orders/{order.id}/action/",
            {"action": "reject", "reason": ""},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.ACCEPTED)
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
        res = self.client.post(
            f"/api/v1/orders/{order.id}/action/",
            {"action": "reject", "reason": "Item unavailable."},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(order.cancel_reason, "Item unavailable.")
        self.assertEqual(tx.status, PaymentStatus.REFUNDED)
        refund_mock.assert_called_once()
