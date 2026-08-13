from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.marketing.models import DiscountType, PromoCode
from apps.users.models import Role, User


class AvailablePromoCodeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="promo-customer",
            email="promo-customer@example.com",
            password="password123",
        )
        customer_role, _ = Role.objects.get_or_create(name="Customer")
        self.customer.roles.add(customer_role)

    def test_customer_sees_only_eligible_promos(self):
        now = timezone.now()
        eligible = PromoCode.objects.create(
            code="SAVE50",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("50.00"),
            min_order_amount=Decimal("100.00"),
            end_date=now + timedelta(days=7),
        )
        PromoCode.objects.create(
            code="MIN500",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("50.00"),
            min_order_amount=Decimal("500.00"),
            end_date=now + timedelta(days=7),
        )
        PromoCode.objects.create(
            code="EXPIRED",
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10.00"),
            start_date=now - timedelta(days=7),
            end_date=now - timedelta(days=1),
        )
        self.client.force_authenticate(self.customer)

        response = self.client.get(
            "/api/v1/marketing/promos/available/",
            {"subtotal": "150.00"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([promo["code"] for promo in response.data], [eligible.code])

    def test_available_promos_require_customer_authentication(self):
        response = self.client.get("/api/v1/marketing/promos/available/")

        self.assertEqual(response.status_code, 401)
