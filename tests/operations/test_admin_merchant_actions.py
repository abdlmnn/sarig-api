from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.models import Order, OrderStatus
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store, StoreManualOverride


class AdminMerchantActionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin-operations",
            email="admin-operations@example.com",
            password="password123",
        )
        self.merchant = User.objects.create_user(
            username="merchant-operations",
            email="merchant-operations@example.com",
            password="password123",
        )
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        self.merchant.roles.add(merchant_role)
        self.customer = User.objects.create_user(
            username="customer-operations",
            email="customer-operations@example.com",
            password="password123",
        )
        vertical, _ = BusinessVertical.objects.get_or_create(
            slug="restaurant",
            defaults={"name": "Restaurant"},
        )
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Operations Restaurant",
            latitude="8.003400",
            longitude="124.283900",
            street_address="Banggolo",
            city="Marawi City",
            commission_rate=Decimal("15.00"),
        )
        self.url = f"/api/v1/operations/merchants/{self.store.id}/action"

    def act(self, action, reason="Reviewed by operations"):
        return self.client.patch(
            self.url,
            {"action": action, "reason": reason},
            format="json",
        )

    def test_admin_can_pause_and_reactivate_account(self):
        self.client.force_authenticate(self.admin)

        self.assertEqual(self.act("PAUSE_ACCOUNT").status_code, 200)
        self.store.refresh_from_db()
        self.assertFalse(self.store.is_active)
        self.assertEqual(self.store.manual_override, StoreManualOverride.PAUSED_ORDERS)

        self.assertEqual(self.act("REACTIVATE_ACCOUNT").status_code, 200)
        self.store.refresh_from_db()
        self.assertTrue(self.store.is_active)
        self.assertIsNone(self.store.manual_override)

    def test_admin_can_stop_orders_and_return_to_schedule(self):
        self.client.force_authenticate(self.admin)

        self.assertEqual(self.act("STOP_ORDERS", "Safety inspection").status_code, 200)
        self.store.refresh_from_db()
        self.assertEqual(self.store.manual_override, StoreManualOverride.CLOSED_TEMPORARILY)

        self.assertEqual(self.act("RETURN_TO_SCHEDULE").status_code, 200)
        self.store.refresh_from_db()
        self.assertIsNone(self.store.manual_override)

    def test_action_requires_reason(self):
        self.client.force_authenticate(self.admin)
        response = self.act("PAUSE_ACCOUNT", "")

        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.data)

    def test_account_cannot_be_paused_with_active_orders(self):
        Order.objects.create(
            customer=self.customer,
            store=self.store,
            status=OrderStatus.PREPARING,
            delivery_address_text="Banggolo, Marawi City",
            delivery_latitude="8.003400",
            delivery_longitude="124.283900",
            subtotal=Decimal("100.00"),
            delivery_fee=Decimal("20.00"),
            system_fee=Decimal("5.00"),
            total_amount=Decimal("125.00"),
        )
        self.client.force_authenticate(self.admin)

        response = self.act("PAUSE_ACCOUNT")

        self.assertEqual(response.status_code, 409)
        self.store.refresh_from_db()
        self.assertTrue(self.store.is_active)

    def test_non_admin_cannot_manage_merchant(self):
        self.client.force_authenticate(self.merchant)

        self.assertEqual(self.act("STOP_ORDERS").status_code, 403)

    def test_admin_merchant_payload_reflects_availability(self):
        self.client.force_authenticate(self.merchant)
        open_toggle = self.client.patch(
            "/api/v1/merchant/store/status/",
            {"status": "OPEN"},
            format="json",
        )
        self.assertEqual(open_toggle.status_code, 200)

        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/operations/merchants")
        self.assertEqual(response.status_code, 200)
        merchant = response.data["data"]["items"][0]
        self.assertTrue(merchant["is_open"])
        self.assertIn("next_status_change", merchant)

        self.client.force_authenticate(self.merchant)
        close_toggle = self.client.patch(
            "/api/v1/merchant/store/status/",
            {"status": "CLOSED"},
            format="json",
        )
        self.assertEqual(close_toggle.status_code, 200)

        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/operations/merchants")
        merchant = response.data["data"]["items"][0]
        self.assertFalse(merchant["is_open"])
