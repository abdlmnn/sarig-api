from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.models import DeliveryMethod, Order, OrderStatus
from apps.payments.models import PaymentMethod, PaymentStatus, PaymentTransaction
from apps.riders.models import RiderOrderOffer, RiderProfile
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store


class RiderDashboardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="dashboard-customer",
            email="dashboard-customer@test.com",
            password="pw12345",
        )
        self.merchant = User.objects.create_user(
            username="dashboard-merchant",
            email="dashboard-merchant@test.com",
            password="pw12345",
        )
        self.rider = User.objects.create_user(
            username="dashboard-rider",
            email="dashboard-rider@test.com",
            password="pw12345",
        )
        rider_role, _ = Role.objects.get_or_create(name="Rider")
        self.rider.roles.add(rider_role)
        self.profile = RiderProfile.objects.create(user=self.rider, is_online=True)
        vertical, _ = BusinessVertical.objects.get_or_create(
            slug="restaurant",
            defaults={"name": "Restaurant"},
        )
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Rider Dashboard Store",
            latitude=Decimal("7.190700"),
            longitude=Decimal("125.455300"),
            street_address="Store Street",
            city="Marawi",
        )

    def create_order(self, status=OrderStatus.READY, rider=None):
        return Order.objects.create(
            customer=self.customer,
            store=self.store,
            rider=rider,
            delivery_method=DeliveryMethod.DELIVERY,
            status=status,
            delivery_address_text="Customer destination",
            delivery_latitude=Decimal("7.200000"),
            delivery_longitude=Decimal("125.460000"),
            subtotal=Decimal("100.00"),
            delivery_fee=Decimal("40.00"),
            system_fee=Decimal("10.00"),
            total_amount=Decimal("150.00"),
            estimated_arrival_time=timezone.now() + timedelta(minutes=20),
        )

    def test_dashboard_requires_rider_role(self):
        RiderProfile.objects.create(user=self.customer)
        self.client.force_authenticate(user=self.customer)

        response = self.client.get("/api/v1/riders/dashboard/")

        self.assertEqual(response.status_code, 403)

    def test_status_toggle_requires_rider_role(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post("/api/v1/riders/status/toggle/")

        self.assertEqual(response.status_code, 403)

    def test_status_update_sets_requested_state_idempotently(self):
        self.client.force_authenticate(user=self.rider)

        first_response = self.client.post(
            "/api/v1/riders/status/toggle/",
            {"is_online": False},
            format="json",
        )
        second_response = self.client.post(
            "/api/v1/riders/status/toggle/",
            {"is_online": False},
            format="json",
        )

        self.profile.refresh_from_db()
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertFalse(first_response.data["is_online"])
        self.assertFalse(second_response.data["is_online"])
        self.assertFalse(self.profile.is_online)

    def test_status_update_preserves_legacy_toggle_without_payload(self):
        self.client.force_authenticate(user=self.rider)

        response = self.client.post("/api/v1/riders/status/toggle/")

        self.profile.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.profile.is_online)

    def test_dashboard_returns_nullable_active_order(self):
        self.client.force_authenticate(user=self.rider)

        response = self.client.get("/api/v1/riders/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["active_order"])
        self.assertEqual(response.data["username"], self.rider.username)

    def test_dashboard_returns_only_one_pending_delivery_offer(self):
        first_order = self.create_order()
        second_order = self.create_order()
        RiderOrderOffer.objects.create(
            order=first_order,
            rider=self.profile,
            expires_at=timezone.now() + timedelta(minutes=1),
        )
        RiderOrderOffer.objects.create(
            order=second_order,
            rider=self.profile,
            expires_at=timezone.now() + timedelta(minutes=2),
        )
        self.client.force_authenticate(user=self.rider)

        response = self.client.get("/api/v1/riders/dashboard/")

        self.assertEqual(len(response.data["delivery_offers"]), 1)
        self.assertEqual(response.data["delivery_offers"][0]["order_id"], str(first_order.id))

    def test_dashboard_returns_least_privilege_ready_order_payload(self):
        order = self.create_order(rider=self.rider)
        self.client.force_authenticate(user=self.rider)

        response = self.client.get("/api/v1/riders/dashboard/")

        self.assertEqual(response.status_code, 200)
        active_order = response.data["active_order"]
        self.assertEqual(
            set(active_order),
            {
                "order_id",
                "display_id",
                "status",
                "store",
                "destination",
                "estimated_arrival_time",
                "available_actions",
                "should_publish_location",
            },
        )
        self.assertEqual(active_order["order_id"], str(order.id))
        self.assertEqual(active_order["display_id"], f"SRG-{str(order.id)[:8].upper()}")
        self.assertEqual(active_order["status"], OrderStatus.READY)
        self.assertEqual(active_order["available_actions"], ["pickup"])
        self.assertTrue(active_order["should_publish_location"])
        self.assertEqual(
            active_order["store"],
            {
                "name": self.store.name,
                "address_text": self.store.street_address,
                "latitude": "7.190700",
                "longitude": "125.455300",
            },
        )
        self.assertEqual(active_order["destination"]["address_text"], "Customer destination")
        self.assertNotIn("customer", active_order)
        self.assertNotIn("total_amount", active_order)

    def test_dashboard_selects_oldest_active_order_deterministically(self):
        newer_order = self.create_order(status=OrderStatus.ON_THE_WAY, rider=self.rider)
        older_order = self.create_order(status=OrderStatus.PREPARING, rider=self.rider)
        Order.objects.filter(id=older_order.id).update(created_at=timezone.now() - timedelta(minutes=10))
        Order.objects.filter(id=newer_order.id).update(created_at=timezone.now() - timedelta(minutes=5))
        self.client.force_authenticate(user=self.rider)

        response = self.client.get("/api/v1/riders/dashboard/")

        self.assertEqual(response.data["active_order"]["order_id"], str(older_order.id))
        self.assertEqual(response.data["active_order"]["available_actions"], [])

    @patch("apps.users.notifications.PushNotificationService.notify_order_status")
    @patch("apps.orders.models.Order.broadcast_status_update")
    def test_pickup_response_returns_authoritative_active_order(self, broadcast, notify):
        order = self.create_order(rider=self.rider)
        self.client.force_authenticate(user=self.rider)

        response = self.client.post(
            f"/api/v1/riders/orders/{order.id}/action/",
            {"action": "pickup"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["active_order"]["status"], OrderStatus.ON_THE_WAY)
        self.assertEqual(response.data["active_order"]["available_actions"], ["delivered"])
        broadcast.assert_called_once()
        notify.assert_called_once()

    @patch("apps.riders.services.RiderDispatcherService.record_delivery_earnings")
    @patch("apps.users.notifications.PushNotificationService.notify_order_status")
    @patch("apps.orders.models.Order.broadcast_status_update")
    def test_delivered_response_clears_active_order(self, broadcast, notify, record_earnings):
        order = self.create_order(status=OrderStatus.ON_THE_WAY, rider=self.rider)
        payment = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=PaymentMethod.COD,
            status=PaymentStatus.PENDING,
        )
        self.profile.is_available = False
        self.profile.save(update_fields=["is_available"])
        self.client.force_authenticate(user=self.rider)

        response = self.client.post(
            f"/api/v1/riders/orders/{order.id}/action/",
            {"action": "delivered"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertIsNone(response.data["active_order"])
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)
        broadcast.assert_called_once()
        notify.assert_called_once()
        record_earnings.assert_called_once_with(order)

    @patch("apps.riders.services.RiderDispatcherService.record_delivery_earnings")
    @patch("apps.users.notifications.PushNotificationService.notify_order_status")
    @patch("apps.orders.models.Order.broadcast_status_update")
    def test_delivery_does_not_complete_pending_online_payment(
        self, broadcast, notify, record_earnings
    ):
        order = self.create_order(status=OrderStatus.ON_THE_WAY, rider=self.rider)
        payment = PaymentTransaction.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=PaymentMethod.PAYMONGO,
            status=PaymentStatus.PENDING,
        )
        self.client.force_authenticate(user=self.rider)

        response = self.client.post(
            f"/api/v1/riders/orders/{order.id}/action/",
            {"action": "delivered"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    @patch("apps.orders.models.Order.broadcast_status_update")
    @patch("apps.riders.services.RiderDispatcherService.notify_rider_pickup_ready")
    def test_accept_offer_response_returns_active_order(self, notify_ready, broadcast):
        order = self.create_order(status=OrderStatus.PREPARING)
        RiderOrderOffer.objects.create(
            order=order,
            rider=self.profile,
            expires_at=timezone.now() + timedelta(minutes=1),
        )
        self.client.force_authenticate(user=self.rider)

        response = self.client.post(
            f"/api/v1/riders/orders/{order.id}/action/",
            {"action": "accept_offer"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["active_order"]["order_id"], str(order.id))
        self.assertEqual(response.data["active_order"]["status"], OrderStatus.PREPARING)
        notify_ready.assert_called_once()
        broadcast.assert_called_once()
