from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Category, MedicineReference, ProductType
from apps.catalog.serializers import ProductSerializer
from apps.users.models import User
from apps.vendors.models import BusinessVertical, Store


class MedicineReferenceTests(TestCase):
    def setUp(self):
        self.reference = MedicineReference.objects.create(
            registration_number="DR-TEST-1",
            generic_name="Amoxicillin",
            brand_name="Testmox",
            dosage_strength="500mg",
            dosage_form="Capsule",
            classification="Prescription Drug (RX)",
            requires_prescription=True,
        )
        owner = User.objects.create_user(username="pharmacy", email="pharmacy@example.com", password="password123")
        vertical, _ = BusinessVertical.objects.update_or_create(
            slug="pharmacy",
            defaults={"name": "Pharmacy", "allowed_product_types": ["medicine", "grocery", "general"]},
        )
        store = Store.objects.create(
            owner=owner,
            vertical=vertical,
            name="Sarig Pharmacy",
            latitude="8.003400",
            longitude="124.283900",
            street_address="Banggolo",
            city="Marawi City",
        )
        self.category = Category.objects.create(store=store, name="Medicine", slug="medicine")

    def test_medicine_reference_search(self):
        response = APIClient().get("/api/v1/catalog/medicine-references/", {"q": "amoxicillin"})

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        self.assertEqual(results[0]["registration_number"], "DR-TEST-1")
        self.assertTrue(results[0]["requires_prescription"])

    def test_product_serializer_prefills_from_medicine_reference(self):
        serializer = ProductSerializer(
            data={
                "category": str(self.category.id),
                "product_type": ProductType.MEDICINE,
                "medicine_reference": str(self.reference.id),
                "name": "Testmox 500mg",
                "price": "15.00",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        product = serializer.save()
        self.assertEqual(product.generic_name, "Amoxicillin")
        self.assertEqual(product.brand_name, "Testmox")
        self.assertEqual(product.dosage, "500mg")
        self.assertEqual(product.medicine_form, "Capsule")
        self.assertTrue(product.requires_prescription)
