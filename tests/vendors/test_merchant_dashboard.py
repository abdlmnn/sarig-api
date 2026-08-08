from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.orders.models import DeliveryMethod, Order, OrderItem, OrderStatus
from apps.catalog.models import Category, Product
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store, StoreManualOverride


def image_upload(name, size=(800, 800)):
    output = BytesIO()
    Image.new("RGB", size, "white").save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


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
            logo_image="stores/logos/test-store.png",
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

    def test_merchant_dashboard_overview_returns_store_payload(self):
        self.client.force_authenticate(self.merchant)
        response = self.client.get("/api/v1/merchant/dashboard/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["merchant"]["business_name"], "Sari Sari Restaurant")
        self.assertIn(response.data["merchant"]["status"], ["OPEN", "CLOSED"])
        self.assertIn("status_label", response.data["merchant"])
        self.assertIn("status_reason", response.data["merchant"])
        self.assertIn("manual_override", response.data["merchant"])
        self.assertIn("next_status_change", response.data["merchant"])

    def test_merchant_dashboard_requires_a_store_logo(self):
        self.store.logo_image = None
        self.store.save(update_fields=["logo_image"])
        self.client.force_authenticate(self.merchant)

        response = self.client.get("/api/v1/merchant/dashboard/overview/")

        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.data["code"], "STORE_LOGO_REQUIRED")

    def test_store_generates_unique_readable_slugs(self):
        duplicate = Store.objects.create(
            owner=self.merchant,
            vertical=self.store.vertical,
            name=self.store.name,
            latitude="8.004000",
            longitude="124.284000",
            street_address="Second Street",
            city="Marawi City",
        )

        self.assertEqual(self.store.slug, "sari-sari-restaurant")
        self.assertEqual(duplicate.slug, "sari-sari-restaurant-2")

    def test_store_slug_does_not_change_after_creation(self):
        original_slug = self.store.slug
        self.store.name = "Renamed Restaurant"
        self.store.slug = "renamed-restaurant"
        self.store.save(update_fields=["name", "slug"])

        self.store.refresh_from_db()
        self.assertEqual(self.store.slug, original_slug)

    def test_store_slug_recovers_from_concurrent_name_collision(self):
        with patch(
            "django.db.models.query.QuerySet.exists",
            side_effect=[False, False, True],
        ):
            duplicate = Store.objects.create(
                owner=self.merchant,
                vertical=self.store.vertical,
                name=self.store.name,
                latitude="8.004000",
                longitude="124.284000",
                street_address="Second Street",
                city="Marawi City",
            )

        self.assertTrue(duplicate.slug.startswith("sari-sari-restaurant-"))
        self.assertNotEqual(duplicate.slug, self.store.slug)

    def test_database_rejects_blank_store_slug_when_save_is_bypassed(self):
        store = Store(
            owner=self.merchant,
            vertical=self.store.vertical,
            name="Bulk Store",
            latitude="8.004000",
            longitude="124.284000",
            street_address="Bulk Street",
            city="Marawi City",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Store.objects.bulk_create([store])

    def test_merchant_order_dashboard_overview_returns_order_payload(self):
        pending = self.create_order(OrderStatus.PENDING, "150.00")
        preparing = self.create_order(OrderStatus.PREPARING, "200.00")
        ready = self.create_order(OrderStatus.READY, "300.00", "MSU Main, Marawi City")
        delivered = self.create_order(OrderStatus.DELIVERED, "400.00")
        delivered.delivered_at = timezone.now()
        delivered.save(update_fields=["delivered_at"])

        self.client.force_authenticate(self.merchant)
        response = self.client.get("/api/v1/orders/store-activity/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stats"]["orders_today"]["value"], 4)
        self.assertEqual(response.data["stats"]["preparing_now"]["value"], 1)
        self.assertEqual(response.data["order_pipeline"]["new"], 1)
        self.assertEqual(response.data["order_pipeline"]["preparing"], 1)
        self.assertEqual(response.data["order_pipeline"]["ready"], 1)
        self.assertEqual(response.data["settlement"]["gross_sales"]["value"], "1050.00")
        self.assertEqual(response.data["settlement"]["fees"]["value"], "157.50")
        self.assertEqual(response.data["settlement"]["expected_payout"]["value"], "892.50")
        self.assertTrue(response.data["active_orders"])
        active_orders = response.data["active_orders"]
        order_ids = [item["order_id"] for item in active_orders]
        self.assertEqual(order_ids, [str(pending.id)])
        self.assertEqual(len(order_ids), len(set(order_ids)))
        self.assertTrue(all(item["status"] == "NEW" for item in active_orders))
        self.assertTrue(all(item["id"].startswith("SRG-") for item in active_orders))
        self.assertTrue(response.data["delivery_lanes"])

    def test_merchant_dashboard_requires_merchant_role(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/v1/orders/store-activity/")

        self.assertEqual(response.status_code, 403)

    def test_merchant_can_view_owned_order_detail(self):
        order = self.create_order(OrderStatus.PENDING)
        self.client.force_authenticate(self.merchant)

        response = self.client.get(f"/api/v1/orders/{order.id}/merchant-detail/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["id"]), str(order.id))
        self.assertEqual(response.data["customer_name"], "Amina P.")
        self.assertEqual(response.data["delivery_method"], DeliveryMethod.DELIVERY)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertIsNone(response.data["tracking"]["rider"])

    def test_merchant_cannot_view_another_merchants_order_detail(self):
        order = self.create_order(OrderStatus.PENDING)
        other_merchant = User.objects.create_user(
            username="other-merchant",
            email="other-merchant@example.com",
            password="password123",
        )
        merchant_role = Role.objects.get(name="Merchant")
        other_merchant.roles.add(merchant_role)
        self.client.force_authenticate(other_merchant)

        response = self.client.get(f"/api/v1/orders/{order.id}/merchant-detail/")

        self.assertEqual(response.status_code, 404)

    def test_order_detail_requires_authentication(self):
        order = self.create_order(OrderStatus.PENDING)

        response = self.client.get(f"/api/v1/orders/{order.id}/merchant-detail/")

        self.assertEqual(response.status_code, 401)

    def test_merchant_order_list_returns_active_orders_oldest_first(self):
        oldest = self.create_order(OrderStatus.PENDING)
        newest = self.create_order(OrderStatus.READY)
        self.create_order(OrderStatus.DELIVERED)
        Order.objects.filter(id=oldest.id).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )
        self.client.force_authenticate(self.merchant)

        response = self.client.get("/api/v1/orders/merchant/?status=ACTIVE")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["order_id"] for item in response.data["orders"]],
            [str(oldest.id), str(newest.id)],
        )
        self.assertEqual(response.data["orders"][0]["status"], "NEW")
        self.assertEqual(
            response.data["orders"][0]["store_vertical_slug"],
            "restaurant",
        )

    def test_merchant_order_list_supports_customer_search(self):
        order = self.create_order(OrderStatus.PENDING)
        self.client.force_authenticate(self.merchant)

        response = self.client.get("/api/v1/orders/merchant/?status=ALL&q=Amina")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["order_id"] for item in response.data["orders"]],
            [str(order.id)],
        )

    def test_merchant_order_list_rejects_invalid_status(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get("/api/v1/orders/merchant/?status=UNKNOWN")

        self.assertEqual(response.status_code, 400)

    def test_merchant_order_list_excludes_another_merchants_orders(self):
        self.create_order(OrderStatus.PENDING)
        other_merchant = User.objects.create_user(
            username="list-merchant",
            email="list-merchant@example.com",
            password="password123",
        )
        other_merchant.roles.add(Role.objects.get(name="Merchant"))
        self.client.force_authenticate(other_merchant)

        response = self.client.get("/api/v1/orders/merchant/?status=ALL")

        self.assertEqual(response.status_code, 404)

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

    def test_merchant_can_update_store_branding(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.patch(
            f"/api/v1/merchant/store/branding/{self.store.id}/",
            {
                "logo_image": image_upload("logo.png"),
                "banner_image": image_upload("banner.png", (1600, 600)),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("logo.png", response.data["logo_image"])
        self.assertIn("banner.png", response.data["banner_image"])

        self.store.refresh_from_db()
        self.assertTrue(self.store.logo_image.name.startswith("stores/logos/"))
        self.assertTrue(self.store.banner_image.name.startswith("stores/banners/"))

        public_response = self.client.get(
            f"/api/v1/catalog/stores/{self.store.id}/"
        )
        self.assertEqual(public_response.status_code, 200)
        self.assertIn("logo.png", public_response.data["logo_image"])

        self.store.logo_image.delete(save=False)
        self.store.banner_image.delete(save=False)

    def test_store_branding_rejects_invalid_upload(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.patch(
            f"/api/v1/merchant/store/branding/{self.store.id}/",
            {
                "logo_image": SimpleUploadedFile(
                    "logo.txt",
                    b"not an image",
                    content_type="text/plain",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)

    def test_store_branding_requires_merchant_role(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/v1/merchant/store/branding/")

        self.assertEqual(response.status_code, 403)

    def test_store_branding_lists_all_owned_active_stores(self):
        second_store = Store.objects.create(
            owner=self.merchant,
            vertical=self.store.vertical,
            name="Second Branch",
            latitude="8.004000",
            longitude="124.284000",
            street_address="Second Street",
            city="Marawi City",
        )
        Store.objects.create(
            owner=self.merchant,
            vertical=self.store.vertical,
            name="Inactive Branch",
            latitude="8.005000",
            longitude="124.285000",
            street_address="Third Street",
            city="Marawi City",
            is_active=False,
        )
        self.client.force_authenticate(self.merchant)

        response = self.client.get("/api/v1/merchant/store/branding/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {store["id"] for store in response.data["stores"]},
            {str(self.store.id), str(second_store.id)},
        )
        first_store = next(
            store
            for store in response.data["stores"]
            if store["id"] == str(self.store.id)
        )
        self.assertIn("status", first_store)
        self.assertIn("status_label", first_store)
        self.assertEqual(first_store["business_category"], self.store.vertical.name)
        self.assertEqual(
            first_store["vertical"],
            {
                "name": self.store.vertical.name,
                "slug": self.store.vertical.slug,
            },
        )

    def test_merchant_cannot_update_another_merchants_branding(self):
        other_merchant = User.objects.create_user(
            username="branding-owner",
            email="branding-owner@example.com",
            password="password123",
        )
        other_merchant.roles.add(Role.objects.get(name="Merchant"))
        other_store = Store.objects.create(
            owner=other_merchant,
            vertical=self.store.vertical,
            name="Other Store",
            latitude="8.006000",
            longitude="124.286000",
            street_address="Other Street",
            city="Marawi City",
        )
        self.client.force_authenticate(self.merchant)

        response = self.client.patch(
            f"/api/v1/merchant/store/branding/{other_store.id}/",
            {"logo_image": image_upload("other-logo.png")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 404)
