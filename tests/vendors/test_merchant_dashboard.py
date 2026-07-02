from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.models import DeliveryMethod, Order, OrderItem, OrderStatus
from apps.catalog.models import Category, Product
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store, StoreManualOverride


class MerchantDashboardOverviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant = User.objects.create_user(username="merchant", email="merchant@example.com", password="password123")
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        self.merchant.roles.add(merchant_role)
        self.customer = User.objects.create_user(username="customer", first_name="Amina", last_name="P.", password="password123")
        vertical, _ = BusinessVertical.objects.update_or_create(
            slug="restaurant",
            defaults={"name": "Restaurant", "allowed_product_types": ["food"]},
        )
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Sari Sari Restaurant",
            latitude="8.003400",
            longitude="124.283900",
            street_address="Banggolo",
            city="Marawi City",
            commission_rate=Decimal("15.00"),
        )
        category = Category.objects.create(store=self.store, name="Meals", slug="meals")
        self.product = Product.objects.create(category=category, name="Chicken biryani", price=Decimal("120.00"))

    def create_order(self, status, total="150.00", address="Downtown Marawi, Marawi City"):
        order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            status=status,
            delivery_method=DeliveryMethod.DELIVERY,
            delivery_address_text=address,
            delivery_latitude="8.003400",
            delivery_longitude="124.283900",
            subtotal=Decimal(total),
            delivery_fee=Decimal("40.00"),
            system_fee=Decimal("10.00"),
            total_amount=Decimal(total),
        )
        OrderItem.objects.create(order=order, product=self.product, quantity=1, unit_price=self.product.price)
        return order

    def test_merchant_dashboard_overview_returns_single_payload(self):
        self.create_order(OrderStatus.PENDING, "150.00")
        self.create_order(OrderStatus.PREPARING, "200.00")
        self.create_order(OrderStatus.READY, "300.00", "MSU Main, Marawi City")
        delivered = self.create_order(OrderStatus.DELIVERED, "400.00")
        delivered.delivered_at = timezone.now()
        delivered.save(update_fields=["delivered_at"])

        self.client.force_authenticate(self.merchant)
        response = self.client.get("/api/v1/merchant/dashboard/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["merchant"]["business_name"], "Sari Sari Restaurant")
        self.assertIn(response.data["merchant"]["status"], ["OPEN", "CLOSED"])
        self.assertIn("status_label", response.data["merchant"])
        self.assertIn("status_reason", response.data["merchant"])
        self.assertIn("manual_override", response.data["merchant"])
        self.assertIn("next_status_change", response.data["merchant"])
        self.assertEqual(response.data["stats"]["orders_today"]["value"], 4)
        self.assertEqual(response.data["stats"]["preparing_now"]["value"], 1)
        self.assertEqual(response.data["order_pipeline"]["new"], 1)
        self.assertEqual(response.data["order_pipeline"]["preparing"], 1)
        self.assertEqual(response.data["order_pipeline"]["ready"], 1)
        self.assertEqual(response.data["settlement"]["gross_sales"]["value"], "1050.00")
        self.assertEqual(response.data["settlement"]["fees"]["value"], "157.50")
        self.assertEqual(response.data["settlement"]["expected_payout"]["value"], "892.50")
        self.assertTrue(response.data["active_orders"])
        self.assertTrue(response.data["delivery_lanes"])

    def test_merchant_dashboard_requires_merchant_role(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/v1/merchant/dashboard/overview/")

        self.assertEqual(response.status_code, 403)

    def test_merchant_can_close_store_temporarily(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.patch(
            "/api/v1/merchant/store/status/",
            {
                "manual_override": StoreManualOverride.CLOSED_TEMPORARILY,
                "reason": "Out of stock",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "CLOSED")
        self.assertEqual(response.data["status_label"], "Closed temporarily")
        self.assertEqual(response.data["status_reason"], "Out of stock")

        self.store.refresh_from_db()
        self.assertEqual(self.store.manual_override, StoreManualOverride.CLOSED_TEMPORARILY)
        self.assertEqual(self.store.manual_override_reason, "Out of stock")

    def test_merchant_can_resume_normal_schedule(self):
        self.store.manual_override = StoreManualOverride.PAUSED_ORDERS
        self.store.manual_override_reason = "Busy"
        self.store.save(update_fields=["manual_override", "manual_override_reason", "updated_at"])
        self.client.force_authenticate(self.merchant)

        response = self.client.patch(
            "/api/v1/merchant/store/status/",
            {
                "manual_override": None,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["manual_override"])

        self.store.refresh_from_db()
        self.assertIsNone(self.store.manual_override)
        self.assertEqual(self.store.manual_override_reason, "")

    def test_merchant_can_update_store_status_with_frontend_status_value(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.patch(
            "/api/v1/merchant/store/status/",
            {
                "status": "CLOSED",
                "reason": "Kitchen break",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "CLOSED")
        self.assertEqual(response.data["manual_override"], StoreManualOverride.CLOSED_TEMPORARILY)

        self.store.refresh_from_db()
        self.assertEqual(self.store.manual_override, StoreManualOverride.CLOSED_TEMPORARILY)
        self.assertEqual(self.store.manual_override_reason, "Kitchen break")

    def test_merchant_can_clear_store_status_with_empty_frontend_value(self):
        self.store.manual_override = StoreManualOverride.CLOSED_TEMPORARILY
        self.store.manual_override_reason = "Kitchen break"
        self.store.save(update_fields=["manual_override", "manual_override_reason", "updated_at"])
        self.client.force_authenticate(self.merchant)

        response = self.client.patch(
            "/api/v1/merchant/store/status/",
            {
                "status": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["manual_override"])

        self.store.refresh_from_db()
        self.assertIsNone(self.store.manual_override)
        self.assertEqual(self.store.manual_override_reason, "")
