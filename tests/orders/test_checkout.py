from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.users.models import User, Role
from apps.vendors.models import Store, BusinessVertical
from apps.catalog.models import Category, Product
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentStatus
from apps.marketing.models import PromoCode, DiscountType
from django.utils import timezone
from datetime import timedelta


@override_settings(
    PAYMONGO_USE_MOCK=True,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_STORE_EAGER_RESULT=False,
    CELERY_RESULT_BACKEND="cache+memory://",
)
class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="customer1", email="customer1@test.com", password="pw12345"
        )
        self.merchant = User.objects.create_user(
            username="merchant1", email="merchant1@test.com", password="pw12345"
        )
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        self.merchant.roles.add(merchant_role)

        vertical, _ = BusinessVertical.objects.get_or_create(
            slug="restaurant",
            defaults={"name": "Restaurant"},
        )
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Test Store",
            latitude=7.190700,
            longitude=125.455300,
            street_address="Sample St",
            city="Marawi",
        )
        self.category = Category.objects.create(store=self.store, name="Meals", slug="meals")
        self.product = Product.objects.create(
            category=self.category, name="Burger", price=Decimal("100.00")
        )
        self.other_merchant = User.objects.create_user(
            username="merchant2", email="merchant2@test.com", password="pw12345"
        )
        self.other_vertical, _ = BusinessVertical.objects.get_or_create(
            slug="cafe",
            defaults={"name": "Cafe"},
        )
        self.other_store = Store.objects.create(
            owner=self.other_merchant,
            vertical=self.other_vertical,
            name="Other Store",
            latitude=7.210000,
            longitude=125.470000,
            street_address="Other St",
            city="Marawi",
        )
        self.other_category = Category.objects.create(
            store=self.other_store, name="Drinks", slug="drinks"
        )
        self.other_product = Product.objects.create(
            category=self.other_category, name="Coffee", price=Decimal("80.00")
        )

    def test_cod_checkout_creates_order_and_payment_transaction(self):
        self.client.force_authenticate(user=self.customer)
        payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.product.id), "quantity": 2}],
            "payment_method": "COD",
            "delivery_method": "PICKUP",
            "address_text": "Home",
            "latitude": "7.190700",
            "longitude": "125.455300",
        }
        res = self.client.post("/api/v1/orders/checkout/", payload, format="json")
        self.assertEqual(res.status_code, 201)
        order = Order.objects.get(id=res.data["order"]["id"])
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.delivery_fee, Decimal("0.00"))
        self.assertEqual(order.system_fee, Decimal("10.00"))
        self.assertEqual(order.total_amount, Decimal("210.00"))
        self.assertTrue(
            PaymentTransaction.objects.filter(
                order=order, payment_method=PaymentMethod.COD
            ).exists()
        )

    def test_paymongo_checkout_returns_checkout_url_and_records_session(self):
        self.client.force_authenticate(user=self.customer)
        payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.product.id), "quantity": 1}],
            "payment_method": "PAYMONGO",
            "delivery_method": "PICKUP",
            "address_text": "Home",
            "latitude": "7.190700",
            "longitude": "125.455300",
        }

        res = self.client.post("/api/v1/orders/checkout/", payload, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "pending")
        self.assertIn("checkout_url", res.data)
        order = Order.objects.get(id=res.data["order"]["id"])
        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.payment_method, PaymentMethod.PAYMONGO)
        self.assertEqual(tx.status, PaymentStatus.PENDING)
        self.assertTrue(tx.external_transaction_id.startswith("cs_mock_"))
        self.assertEqual(tx.provider_raw_response["attributes"]["metadata"]["order_id"], str(order.id))

    def test_checkout_rejects_product_from_different_store(self):
        self.client.force_authenticate(user=self.customer)
        payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.other_product.id), "quantity": 1}],
            "payment_method": "COD",
            "delivery_method": "PICKUP",
            "address_text": "Home",
            "latitude": "7.190700",
            "longitude": "125.455300",
        }
        res = self.client.post("/api/v1/orders/checkout/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not belong to this store", res.data["error"])

    def test_checkout_rejects_prescription_required_product(self):
        self.product.product_type = "medicine"
        self.product.requires_prescription = True
        self.product.save()
        self.client.force_authenticate(user=self.customer)
        payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.product.id), "quantity": 1}],
            "payment_method": "COD",
            "delivery_method": "PICKUP",
            "address_text": "Home",
            "latitude": "7.190700",
            "longitude": "125.455300",
        }

        res = self.client.post("/api/v1/orders/checkout/", payload, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "Product Burger requires a prescription.")

    def test_checkout_requires_store_and_items(self):
        self.client.force_authenticate(user=self.customer)
        res = self.client.post(
            "/api/v1/orders/checkout/",
            {"payment_method": "COD"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "Store ID and items are required.")

    def test_checkout_rejects_invalid_promo_code(self):
        self.client.force_authenticate(user=self.customer)
        payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.product.id), "quantity": 1}],
            "payment_method": "COD",
            "delivery_method": "PICKUP",
            "promo_code": "NOTREAL",
            "address_text": "Home",
            "latitude": "7.190700",
            "longitude": "125.455300",
        }
        res = self.client.post("/api/v1/orders/checkout/", payload, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "Invalid promo code.")

    @patch("apps.locations.services.route_estimate")
    def test_delivery_checkout_uses_location_service_fee(self, mock_route_estimate):
        mock_route_estimate.return_value = {
            "distance_km": Decimal("2.40"),
            "duration_minutes": 8,
            "provider": "openrouteservice",
            "route_geometry": None,
        }
        self.client.force_authenticate(user=self.customer)
        payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.product.id), "quantity": 1}],
            "payment_method": "COD",
            "delivery_method": "DELIVERY",
            "address_text": "Home",
            "latitude": "7.200000",
            "longitude": "125.460000",
        }

        res = self.client.post("/api/v1/orders/checkout/", payload, format="json")

        self.assertEqual(res.status_code, 201)
        order = Order.objects.get(id=res.data["order"]["id"])
        self.assertEqual(order.delivery_fee, Decimal("64.00"))
        mock_route_estimate.assert_called_once()

    @override_settings(DELIVERY_MAX_DISTANCE_KM=1)
    @patch("apps.locations.services.route_estimate")
    def test_delivery_checkout_rejects_far_address(self, mock_route_estimate):
        mock_route_estimate.return_value = {
            "distance_km": Decimal("2.40"),
            "duration_minutes": 8,
            "provider": "openrouteservice",
            "route_geometry": None,
        }
        self.client.force_authenticate(user=self.customer)
        payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.product.id), "quantity": 1}],
            "payment_method": "COD",
            "delivery_method": "DELIVERY",
            "address_text": "Home",
            "latitude": "7.200000",
            "longitude": "125.460000",
        }

        res = self.client.post("/api/v1/orders/checkout/", payload, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "Delivery address is outside the supported distance.")
