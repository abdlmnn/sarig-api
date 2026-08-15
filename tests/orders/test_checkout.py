from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.users.models import User, Role
from apps.vendors.models import BusinessVertical, Store, StoreManualOverride
from apps.catalog.models import Category, ModifierGroup, ModifierItem, Product
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
        customer_role, _ = Role.objects.get_or_create(name="Customer")
        self.customer.roles.add(customer_role)
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
            is_open=True,
            is_active=True,
            manual_override=StoreManualOverride.OPEN_NOW,
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
            is_open=True,
            is_active=True,
            manual_override=StoreManualOverride.OPEN_NOW,
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
        self.assertEqual(
            res.data["tracking_url"],
            f"http://testserver/api/v1/orders/{order.id}/",
        )
        self.assertIn("tracking", res.data["order"])
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.delivery_fee, Decimal("0.00"))
        self.assertEqual(order.system_fee, Decimal("10.00"))
        self.assertEqual(order.total_amount, Decimal("210.00"))
        self.assertTrue(
            PaymentTransaction.objects.filter(
                order=order, payment_method=PaymentMethod.COD
            ).exists()
        )

    @patch("apps.orders.tasks.notify_cod_order_created.delay")
    @patch("apps.orders.views._broadcast_order_created")
    def test_cod_checkout_broadcasts_after_commit_without_waiting_for_celery(
        self, broadcast_order_created, queue_notification
    ):
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

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/orders/checkout/", payload, format="json"
            )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data["order"]["id"])
        broadcast_order_created.assert_called_once_with(order)
        queue_notification.assert_called_once_with(str(order.id))

    def test_pickup_quote_returns_final_totals_without_creating_order(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            "/api/v1/orders/checkout/quote/",
            {
                "store_id": str(self.store.id),
                "items": [{"product_id": str(self.product.id), "quantity": 2}],
                "payment_method": "COD",
                "delivery_method": "PICKUP",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subtotal"], "200.00")
        self.assertEqual(response.data["delivery_fee"], "0.00")
        self.assertEqual(response.data["service_fee"], "10.00")
        self.assertEqual(response.data["discount_amount"], "0.00")
        self.assertEqual(response.data["total_amount"], "210.00")
        self.assertEqual(response.data["estimated_minutes"], 10)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_recalculates_after_quoted_product_price_changes(self):
        self.client.force_authenticate(user=self.customer)
        payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.product.id), "quantity": 1}],
            "payment_method": "COD",
            "delivery_method": "PICKUP",
        }
        quote = self.client.post(
            "/api/v1/orders/checkout/quote/",
            payload,
            format="json",
        )
        self.assertEqual(quote.data["total_amount"], "110.00")

        self.product.price = Decimal("125.00")
        self.product.save(update_fields=["price"])
        checkout = self.client.post(
            "/api/v1/orders/checkout/",
            payload,
            format="json",
        )

        self.assertEqual(checkout.status_code, 201)
        order = Order.objects.get(id=checkout.data["order"]["id"])
        self.assertEqual(order.total_amount, Decimal("135.00"))

    def test_quote_accepts_multiple_optional_modifier_choices(self):
        group = ModifierGroup.objects.create(
            product=self.product,
            name="Choose your drink",
            max_selections=1,
            is_required=False,
        )
        mango = ModifierItem.objects.create(
            group=group,
            name="Mango Shake",
            extra_price=Decimal("45.00"),
        )
        tea = ModifierItem.objects.create(
            group=group,
            name="Iced Tea",
            extra_price=Decimal("35.00"),
        )
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            "/api/v1/orders/checkout/quote/",
            {
                "store_id": str(self.store.id),
                "items": [
                    {
                        "product_id": str(self.product.id),
                        "quantity": 1,
                        "modifier_item_ids": [str(mango.id), str(tea.id)],
                    }
                ],
                "payment_method": "COD",
                "delivery_method": "PICKUP",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subtotal"], "180.00")
        self.assertEqual(response.data["total_amount"], "190.00")

    def test_checkout_quote_requires_customer_authentication(self):
        response = self.client.post(
            "/api/v1/orders/checkout/quote/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    @patch("apps.locations.services.route_estimate")
    def test_delivery_quote_returns_fee_distance_and_eta(self, mock_route):
        mock_route.return_value = {
            "distance_km": Decimal("2.40"),
            "duration_minutes": 8,
            "provider": "openrouteservice",
            "route_geometry": None,
        }
        self.product.preparation_time_minutes = 12
        self.product.save(update_fields=["preparation_time_minutes"])
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            "/api/v1/orders/checkout/quote/",
            {
                "store_id": str(self.store.id),
                "items": [{"product_id": str(self.product.id), "quantity": 1}],
                "payment_method": "COD",
                "delivery_method": "DELIVERY",
                "address_text": "Home",
                "latitude": "7.200000123456",
                "longitude": "125.460000654321",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["delivery_fee"], "64.00")
        self.assertEqual(response.data["distance_km"], "2.40")
        self.assertEqual(response.data["estimated_minutes"], 20)
        destination = mock_route.call_args.args[1]
        self.assertEqual(destination["latitude"], Decimal("7.200000"))
        self.assertEqual(destination["longitude"], Decimal("125.460001"))

    @patch("apps.locations.services.route_estimate")
    def test_delivery_quote_adjusts_fee_and_eta_by_delivery_option(self, mock_route):
        mock_route.return_value = {
            "distance_km": Decimal("2.00"),
            "duration_minutes": 10,
            "provider": "openrouteservice",
            "route_geometry": None,
        }
        self.client.force_authenticate(user=self.customer)
        base_payload = {
            "store_id": str(self.store.id),
            "items": [{"product_id": str(self.product.id), "quantity": 1}],
            "payment_method": "COD",
            "delivery_method": "DELIVERY",
            "address_text": "Home",
            "latitude": "7.200000",
            "longitude": "125.460000",
        }

        saver = self.client.post(
            "/api/v1/orders/checkout/quote/",
            {**base_payload, "delivery_option": "SAVER"},
            format="json",
        )
        priority = self.client.post(
            "/api/v1/orders/checkout/quote/",
            {**base_payload, "delivery_option": "PRIORITY"},
            format="json",
        )

        self.assertEqual(saver.status_code, 200)
        self.assertEqual(priority.status_code, 200)
        self.assertEqual(saver.data["delivery_fee"], "51.00")
        self.assertEqual(priority.data["delivery_fee"], "75.00")
        self.assertEqual(
            saver.data["delivery_options"],
            [
                {
                    "value": "SAVER",
                    "label": "Saver",
                    "delivery_fee": "51.00",
                    "estimated_minutes": 30,
                },
                {
                    "value": "STANDARD",
                    "label": "Standard",
                    "delivery_fee": "60.00",
                    "estimated_minutes": 20,
                },
                {
                    "value": "PRIORITY",
                    "label": "Priority",
                    "delivery_fee": "75.00",
                    "estimated_minutes": 15,
                },
            ],
        )
        self.assertGreater(
            saver.data["estimated_minutes"],
            priority.data["estimated_minutes"],
        )

    @patch("apps.locations.services.route_estimate")
    def test_checkout_persists_delivery_option(self, mock_route):
        mock_route.return_value = {
            "distance_km": Decimal("2.00"),
            "duration_minutes": 10,
            "provider": "openrouteservice",
            "route_geometry": None,
        }
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            "/api/v1/orders/checkout/",
            {
                "store_id": str(self.store.id),
                "items": [{"product_id": str(self.product.id), "quantity": 1}],
                "payment_method": "COD",
                "delivery_method": "DELIVERY",
                "delivery_option": "PRIORITY",
                "address_text": "Home",
                "latitude": "7.200000",
                "longitude": "125.460000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(id=response.data["order"]["id"])
        self.assertEqual(order.delivery_option, "PRIORITY")

    def test_delivery_quote_rejects_invalid_coordinate(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            "/api/v1/orders/checkout/quote/",
            {
                "store_id": str(self.store.id),
                "items": [{"product_id": str(self.product.id), "quantity": 1}],
                "payment_method": "COD",
                "delivery_method": "DELIVERY",
                "address_text": "Home",
                "latitude": "NaN",
                "longitude": "125.460000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("latitude", response.data)

    def test_delivery_quote_rejects_out_of_range_coordinate(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            "/api/v1/orders/checkout/quote/",
            {
                "store_id": str(self.store.id),
                "items": [{"product_id": str(self.product.id), "quantity": 1}],
                "payment_method": "COD",
                "delivery_method": "DELIVERY",
                "address_text": "Home",
                "latitude": "91.000000123456",
                "longitude": "125.460000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("latitude", response.data)

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
