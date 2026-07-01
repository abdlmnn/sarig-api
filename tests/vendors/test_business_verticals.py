from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Category, ProductType
from apps.catalog.serializers import ProductSerializer
from apps.users.models import User
from apps.vendors.models import BusinessVertical, Store


class BusinessVerticalRuleTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="merchant", email="merchant@example.com", password="password123")
        self.restaurant, _ = BusinessVertical.objects.update_or_create(
            slug="restaurant",
            defaults={"name": "Restaurant", "allowed_product_types": ["food"]},
        )
        self.pharmacy, _ = BusinessVertical.objects.update_or_create(
            slug="pharmacy",
            defaults={
                "name": "Pharmacy",
                "allowed_product_types": ["medicine", "grocery", "general"],
                "requires_license": True,
                "required_documents": ["mayors_permit", "pharmacy_license"],
            },
        )

    def create_store(self, vertical):
        return Store.objects.create(
            owner=self.owner,
            vertical=vertical,
            name=f"{vertical.name} Store",
            latitude="8.003400",
            longitude="124.283900",
            street_address="Banggolo",
            city="Marawi City",
        )

    def test_restaurant_rejects_medicine_product(self):
        store = self.create_store(self.restaurant)
        category = Category.objects.create(store=store, name="Menu", slug="menu")
        serializer = ProductSerializer(
            data={
                "category": str(category.id),
                "product_type": ProductType.MEDICINE,
                "name": "Amoxicillin",
                "price": "15.00",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("product_type", serializer.errors)

    def test_pharmacy_accepts_medicine_product(self):
        store = self.create_store(self.pharmacy)
        category = Category.objects.create(store=store, name="Medicine", slug="medicine")
        serializer = ProductSerializer(
            data={
                "category": str(category.id),
                "product_type": ProductType.MEDICINE,
                "name": "Amoxicillin",
                "price": "15.00",
                "requires_prescription": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        product = serializer.save()
        self.assertTrue(product.requires_prescription)

    def test_business_verticals_alias_is_public(self):
        client = APIClient()

        response = client.get("/api/v1/vendors/business-verticals/")

        self.assertEqual(response.status_code, 200)
        items = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        self.assertTrue(any(item["slug"] == "pharmacy" for item in items))
