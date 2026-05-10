from decimal import Decimal
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.users.models import User, Role
from apps.vendors.models import Store, BusinessVertical
from apps.catalog.models import Category, Product
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction, PaymentMethod


@override_settings(
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

        vertical = BusinessVertical.objects.create(name="Restaurant", slug="restaurant")
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
