from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Category, InventoryMode, Product, ProductType
from apps.catalog.serializers import ProductSerializer
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store


class ProductArchitectureTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(username="merchant", email="merchant@example.com", password="password123")
        vertical = BusinessVertical.objects.create(name="Mixed Store", slug="mixed-store")
        self.store = Store.objects.create(
            owner=owner,
            vertical=vertical,
            name="Sarig Mixed Store",
            latitude="8.003400",
            longitude="124.283900",
            street_address="Banggolo",
            city="Marawi City",
        )
        self.category = Category.objects.create(store=self.store, name="Products", slug="products")

    def test_food_product_uses_availability_without_stock(self):
        product = Product.objects.create(
            category=self.category,
            product_type=ProductType.FOOD,
            name="Chicken Pastil",
            price=Decimal("65.00"),
            is_available=True,
        )

        self.assertEqual(product.inventory_mode, InventoryMode.NONE)
        self.assertFalse(product.track_inventory)
        self.assertIsNone(product.stock_quantity)
        self.assertTrue(product.in_stock)

    def test_medicine_can_require_prescription(self):
        product = Product.objects.create(
            category=self.category,
            product_type=ProductType.MEDICINE,
            name="Amoxicillin",
            generic_name="Amoxicillin",
            dosage="500mg",
            medicine_form="Capsule",
            requires_prescription=True,
            unit_type="capsule",
            price=Decimal("15.00"),
        )

        self.assertTrue(product.requires_prescription)

    def test_non_medicine_cannot_require_prescription(self):
        serializer = ProductSerializer(
            data={
                "category": str(self.category.id),
                "product_type": ProductType.GROCERY,
                "name": "Rice",
                "price": "55.00",
                "unit_type": "kilo",
                "requires_prescription": True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("requires_prescription", serializer.errors)

    def test_simple_stock_mode_syncs_legacy_track_inventory(self):
        product = Product.objects.create(
            category=self.category,
            product_type=ProductType.GROCERY,
            name="Rice",
            price=Decimal("55.00"),
            unit_type="kilo",
            inventory_mode=InventoryMode.SIMPLE_STOCK,
            stock_quantity=100,
        )

        self.assertTrue(product.track_inventory)
        self.assertEqual(product.stock_quantity, 100)

    def test_simple_stock_requires_quantity(self):
        serializer = ProductSerializer(
            data={
                "category": str(self.category.id),
                "product_type": ProductType.GROCERY,
                "name": "Rice",
                "price": "55.00",
                "unit_type": "kilo",
                "inventory_mode": InventoryMode.SIMPLE_STOCK,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("stock_quantity", serializer.errors)


class CatalogProductManagementRouteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant = User.objects.create_user(username="merchant", email="merchant@example.com", password="password123")
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        self.merchant.roles.add(merchant_role)
        self.customer = User.objects.create_user(username="customer", email="customer@example.com", password="password123")
        vertical, _ = BusinessVertical.objects.update_or_create(
            slug="restaurant",
            defaults={"name": "Restaurant", "allowed_product_types": ["food"]},
        )
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Sarig Restaurant",
            latitude="8.003400",
            longitude="124.283900",
            street_address="Banggolo",
            city="Marawi City",
        )
        self.category = Category.objects.create(store=self.store, name="Meals", slug="meals")
        Product.objects.create(category=self.category, name="Chicken Pastil", price=Decimal("65.00"))

    def test_public_catalog_products_route_remains_read_only_browsing(self):
        response = self.client.get("/api/v1/catalog/products/")

        self.assertEqual(response.status_code, 200)

    def test_catalog_product_management_route_requires_merchant(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get("/api/v1/catalog/products/manage/")

        self.assertEqual(response.status_code, 403)

    def test_catalog_product_management_route_returns_merchant_products(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get("/api/v1/catalog/products/manage/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total_products"], 1)
        self.assertEqual(response.data["products"][0]["name"], "Chicken Pastil")
