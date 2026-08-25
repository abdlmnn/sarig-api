from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase

from apps.orders.models import Order, OrderItem, OrderStatus
from apps.users.models import User
from apps.vendors.models import BusinessVertical, Store


class OrderItemModelTests(SimpleTestCase):
    def test_total_price_returns_none_for_incomplete_item(self):
        item = OrderItem(quantity=1)

        self.assertIsNone(item.total_price)

    def test_total_price_multiplies_quantity_and_unit_price(self):
        item = OrderItem(quantity=2, unit_price=Decimal("12.50"))

        self.assertEqual(item.total_price, Decimal("25.00"))


class OrderRiderInvariantTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="model-customer",
            email="model-customer@test.com",
            password="pw12345",
        )
        self.merchant = User.objects.create_user(
            username="model-merchant",
            email="model-merchant@test.com",
            password="pw12345",
        )
        self.admin_user = User.objects.create_superuser(
            username="model-admin",
            email="model-admin@test.com",
            password="pw12345",
        )
        vertical, _ = BusinessVertical.objects.get_or_create(
            slug="restaurant",
            defaults={"name": "Restaurant"},
        )
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Model Store",
            latitude=Decimal("7.190700"),
            longitude=Decimal("125.455300"),
            street_address="Model Street",
            city="Marawi",
        )
        self.order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            status=OrderStatus.PREPARING,
            delivery_address_text="Customer destination",
            delivery_latitude=Decimal("7.200000"),
            delivery_longitude=Decimal("125.460000"),
            subtotal=Decimal("100.00"),
            delivery_fee=Decimal("40.00"),
            system_fee=Decimal("10.00"),
            total_amount=Decimal("150.00"),
        )

    def test_model_validation_requires_rider_for_delivery_progress_statuses(self):
        message = "A rider must be assigned before an order can be on the way or delivered."

        for invalid_status in [OrderStatus.ON_THE_WAY, OrderStatus.DELIVERED]:
            with self.subTest(status=invalid_status):
                self.order.status = invalid_status
                with self.assertRaisesMessage(ValidationError, message):
                    self.order.full_clean()

        self.order.status = OrderStatus.PREPARING
        self.order.full_clean()

    def test_admin_form_rejects_on_the_way_without_rider(self):
        request = RequestFactory().post("/admin/orders/order/")
        request.user = self.admin_user
        order_admin = admin.site._registry[Order]
        form_class = order_admin.get_form(request, obj=self.order)
        form = form_class(
            data={
                "status": OrderStatus.ON_THE_WAY,
                "delivery_method": self.order.delivery_method,
                "delivery_address_text": self.order.delivery_address_text,
                "delivery_latitude": self.order.delivery_latitude,
                "delivery_longitude": self.order.delivery_longitude,
                "estimated_arrival_time": "",
                "promo_code": "",
                "discount_amount": self.order.discount_amount,
                "delivery_fee": self.order.delivery_fee,
                "system_fee": self.order.system_fee,
            },
            instance=self.order,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "A rider must be assigned before an order can be on the way or delivered.",
            form.non_field_errors(),
        )
