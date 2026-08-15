from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import (
    Category,
    InventoryMode,
    ModifierGroup,
    ModifierItem,
    Product,
    ProductType,
)
from apps.catalog.serializers import ProductSerializer
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store, StoreManualOverride


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
            is_open=True,
            is_active=True,
            manual_override=StoreManualOverride.OPEN_NOW,
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

    def test_catalog_product_management_route_returns_linked_modifier_items(self):
        self.client.force_authenticate(self.merchant)
        product = Product.objects.get(name="Chicken Pastil")
        linked_product = Product.objects.create(
            category=self.category,
            name="Extra Rice",
            price=Decimal("20.00"),
        )
        group = ModifierGroup.objects.create(product=product, name="Add-ons")
        ModifierItem.objects.create(
            group=group,
            linked_product=linked_product,
            name="Extra Rice",
            extra_price=Decimal("20.00"),
        )

        response = self.client.get("/api/v1/catalog/products/manage/")

        self.assertEqual(response.status_code, 200)
        product_payload = next(
            item
            for item in response.data["products"]
            if item["name"] == "Chicken Pastil"
        )
        modifier_groups = product_payload["modifier_groups"]
        self.assertEqual(modifier_groups[0]["name"], "Add-ons")
        self.assertEqual(
            modifier_groups[0]["items"][0]["linked_product"],
            str(linked_product.id),
        )

    def test_restaurant_product_management_patch_updates_product(self):
        self.client.force_authenticate(self.merchant)
        product = Product.objects.get(name="Chicken Pastil")

        response = self.client.patch(
            f"/api/v1/catalog/products/manage/{product.id}/",
            {
                "category": str(self.category.id),
                "name": "Chicken Pastil Special",
                "description": "Updated meal",
                "price": "75.00",
                "product_type": "food",
                "inventory_mode": "none",
                "is_available": "true",
                "track_inventory": "false",
                "preparation_time_minutes": "15",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.name, "Chicken Pastil Special")
        self.assertEqual(product.price, Decimal("75.00"))
        self.assertFalse(product.track_inventory)
        self.assertIsNone(product.stock_quantity)

    def test_public_search_returns_customer_marketplace_fields(self):
        response = self.client.get(
            "/api/v1/catalog/search/",
            {"vertical": "restaurant", "max_price": "100"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["total_items"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["name"], "Chicken Pastil")
        self.assertEqual(result["store"]["name"], "Sarig Restaurant")
        self.assertEqual(result["store"]["vertical"]["slug"], "restaurant")
        self.assertEqual(result["category"]["slug"], "meals")

    def test_public_search_lists_closed_store_products_last(self):
        closed_store = Store.objects.create(
            owner=self.merchant,
            vertical=self.store.vertical,
            name="Closed Restaurant",
            latitude="8.004000",
            longitude="124.284000",
            street_address="Marawi",
            city="Marawi City",
            is_open=False,
        )
        closed_category = Category.objects.create(
            store=closed_store,
            name="Meals",
            slug="meals",
        )
        Product.objects.create(
            category=closed_category,
            name="Lower Priced Meal",
            price=Decimal("10.00"),
        )

        response = self.client.get(
            "/api/v1/catalog/search/",
            {"vertical": "restaurant", "sort": "price_low"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["store"]["is_open"], True)
        self.assertEqual(response.data["results"][-1]["store"]["is_open"], False)

    def test_public_search_excludes_products_without_stock(self):
        product = Product.objects.get(name="Chicken Pastil")
        product.inventory_mode = InventoryMode.SIMPLE_STOCK
        product.stock_quantity = 0
        product.save()

        response = self.client.get("/api/v1/catalog/search/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["total_items"], 0)

    def test_product_comparison_finds_same_medicine_across_pharmacies(self):
        pharmacy_vertical, _ = BusinessVertical.objects.update_or_create(
            slug="pharmacy",
            defaults={
                "name": "Pharmacy",
                "allowed_product_types": ["medicine"],
            },
        )
        first_store = Store.objects.create(
            owner=self.merchant,
            vertical=pharmacy_vertical,
            name="First Pharmacy",
            latitude="8.003400",
            longitude="124.283900",
            street_address="Banggolo",
            city="Marawi City",
        )
        second_store = Store.objects.create(
            owner=self.merchant,
            vertical=pharmacy_vertical,
            name="Second Pharmacy",
            latitude="8.004000",
            longitude="124.284000",
            street_address="Saduc",
            city="Marawi City",
        )
        first_category = Category.objects.create(
            store=first_store,
            name="Pain Relief",
            slug="pain-relief",
        )
        second_category = Category.objects.create(
            store=second_store,
            name="Pain Relief",
            slug="pain-relief",
        )
        selected = Product.objects.create(
            category=first_category,
            name="Paracetamol 500mg",
            generic_name="Paracetamol",
            dosage="500mg",
            product_type=ProductType.MEDICINE,
            price=Decimal("15.00"),
        )
        cheaper = Product.objects.create(
            category=second_category,
            name="Paracetamol Tablet",
            generic_name="Paracetamol",
            dosage="500mg",
            product_type=ProductType.MEDICINE,
            price=Decimal("8.00"),
        )
        Product.objects.create(
            category=second_category,
            name="Paracetamol 250mg",
            generic_name="Paracetamol",
            dosage="250mg",
            product_type=ProductType.MEDICINE,
            price=Decimal("5.00"),
        )

        response = self.client.get(
            "/api/v1/catalog/compare/",
            {"product_id": str(selected.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["options"]), 2)
        self.assertEqual(
            response.data["summary"]["lowest_price_product_id"],
            str(cheaper.id),
        )
        self.assertEqual(
            response.data["summary"]["potential_savings"],
            Decimal("7.00"),
        )

    def test_public_store_list_returns_store_facets_and_public_fields(self):
        response = self.client.get("/api/v1/catalog/stores/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["total_items"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Sarig Restaurant")
        self.assertEqual(response.data["results"][0]["slug"], "sarig-restaurant")
        self.assertEqual(
            response.data["results"][0]["vertical"]["slug"],
            "restaurant",
        )
        self.assertEqual(response.data["facets"]["verticals"][0]["store_count"], 1)
        self.assertNotIn("owner", response.data["results"][0])
        self.assertNotIn("company_email", response.data["results"][0])

    def test_public_store_detail_returns_only_active_store_with_products(self):
        response = self.client.get(f"/api/v1/catalog/stores/{self.store.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.store.id))
        self.assertEqual(response.data["categories"][0]["slug"], "meals")

        slug_response = self.client.get(
            f"/api/v1/catalog/stores/{self.store.slug}/"
        )
        self.assertEqual(slug_response.status_code, 200)
        self.assertEqual(slug_response.data["id"], str(self.store.id))

        Product.objects.filter(category=self.category).update(is_available=False)
        response = self.client.get(f"/api/v1/catalog/stores/{self.store.id}/")

        self.assertEqual(response.status_code, 404)

    def test_public_store_discovery_groups_stores_by_vertical(self):
        response = self.client.get("/api/v1/catalog/stores/discovery/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["groups"]), 1)
        self.assertEqual(
            response.data["groups"][0]["vertical"]["slug"],
            "restaurant",
        )
        self.assertEqual(response.data["groups"][0]["total_stores"], 1)
        self.assertEqual(
            response.data["groups"][0]["stores"][0]["name"],
            "Sarig Restaurant",
        )

    def test_public_store_list_filters_rating_and_returns_location_eta(self):
        response = self.client.get(
            "/api/v1/catalog/stores/",
            {
                "lat": "8.003500",
                "lng": "124.284000",
                "min_rating": "4.5",
                "max_distance": "5",
            },
        )

        self.assertEqual(response.status_code, 200)
        store = response.data["results"][0]
        self.assertIsNotNone(store["distance_km"])
        self.assertIsNotNone(store["delivery_eta_minutes"])
        self.assertIsNotNone(store["delivery_fee"])

    def test_public_store_list_sorts_by_fastest_delivery(self):
        farther_store = Store.objects.create(
            owner=self.merchant,
            vertical=self.store.vertical,
            name="Farther Restaurant",
            latitude="8.030000",
            longitude="124.310000",
            street_address="Marawi",
            city="Marawi City",
        )
        farther_category = Category.objects.create(
            store=farther_store,
            name="Meals",
            slug="meals",
        )
        Product.objects.create(
            category=farther_category,
            name="Farther Meal",
            price=Decimal("80.00"),
        )

        response = self.client.get(
            "/api/v1/catalog/stores/",
            {
                "lat": "8.003500",
                "lng": "124.284000",
                "sort": "fastest",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["name"], "Sarig Restaurant")

    def test_public_store_products_are_scoped_to_selected_store(self):
        other_store = Store.objects.create(
            owner=self.merchant,
            vertical=self.store.vertical,
            name="Other Restaurant",
            latitude="8.004000",
            longitude="124.284000",
            street_address="Marawi",
            city="Marawi City",
        )
        other_category = Category.objects.create(
            store=other_store,
            name="Meals",
            slug="meals",
        )
        Product.objects.create(
            category=other_category,
            name="Other Meal",
            price=Decimal("80.00"),
        )

        response = self.client.get(
            f"/api/v1/catalog/stores/{self.store.slug}/products/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pagination"]["total_items"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Chicken Pastil")
