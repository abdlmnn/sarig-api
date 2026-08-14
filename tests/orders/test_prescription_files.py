from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.models import DeliveryMethod, Order, OrderPrescription, OrderStatus
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store


class PrescriptionFileAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="customer1", email="customer1@test.com", password="pw12345"
        )
        customer_role, _ = Role.objects.get_or_create(name="Customer")
        self.customer.roles.add(customer_role)

        self.other_customer = User.objects.create_user(
            username="customer2", email="customer2@test.com", password="pw12345"
        )
        self.other_customer.roles.add(customer_role)

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
            name="Test Pharmacy",
            latitude=7.190700,
            longitude=125.455300,
            street_address="Sample St",
            city="Marawi",
        )
        self.order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            status=OrderStatus.PENDING,
            delivery_method=DeliveryMethod.PICKUP,
            delivery_address_text="Home",
            delivery_latitude=Decimal("7.190700"),
            delivery_longitude=Decimal("125.455300"),
            subtotal=Decimal("100.00"),
            delivery_fee=Decimal("0.00"),
            system_fee=Decimal("10.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("110.00"),
        )
        self.prescription = OrderPrescription.objects.create(
            order=self.order,
            file=SimpleUploadedFile(
                "rx.png",
                b"\x89PNG\r\n\x1a\nfakepngdata",
                content_type="image/png",
            ),
        )

    def file_url(self):
        return f"/api/v1/orders/prescriptions/{self.prescription.id}/file/"

    def test_customer_can_download_own_prescription(self):
        self.client.force_authenticate(user=self.customer)
        res = self.client.get(self.file_url())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/png")

    def test_other_customer_is_denied(self):
        self.client.force_authenticate(user=self.other_customer)
        res = self.client.get(self.file_url())
        self.assertEqual(res.status_code, 403)

    def test_store_owner_can_download_prescription(self):
        self.client.force_authenticate(user=self.merchant)
        res = self.client.get(self.file_url())
        self.assertEqual(res.status_code, 200)

    def test_unauthenticated_request_is_denied(self):
        res = self.client.get(self.file_url())
        self.assertEqual(res.status_code, 401)

    def test_assigned_rider_can_download_prescription(self):
        rider = User.objects.create_user(
            username="rider1", email="rider1@test.com", password="pw12345"
        )
        rider_role, _ = Role.objects.get_or_create(name="Rider")
        rider.roles.add(rider_role)
        self.order.rider = rider
        self.order.save(update_fields=["rider"])

        self.client.force_authenticate(user=rider)
        res = self.client.get(self.file_url())
        self.assertEqual(res.status_code, 200)

    def test_order_serializer_returns_protected_file_url(self):
        from rest_framework.test import APIRequestFactory

        from apps.orders.serializers import OrderSerializer

        request = APIRequestFactory().get(self.file_url())
        request.user = self.customer
        data = OrderSerializer(self.order, context={"request": request}).data
        file_url = data["prescriptions"][0]["file_url"]
        self.assertTrue(file_url.endswith(self.file_url().split("?")[0]))
        self.assertNotIn("/media/", file_url)
