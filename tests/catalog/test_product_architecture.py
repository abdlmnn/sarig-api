from decimal import Decimal

from django.test import TestCase

from apps.catalog.models import Category, InventoryMode, Product, ProductType
from apps.catalog.serializers import ProductSerializer
from apps.users.models import User
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
