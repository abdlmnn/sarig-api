from django.test import TestCase

from apps.onboarding.serializers import MerchantApplicationSerializer
from apps.vendors.models import BusinessVertical


class MerchantVerticalSerializerTests(TestCase):
    def setUp(self):
        self.pharmacy, _ = BusinessVertical.objects.update_or_create(
            slug="pharmacy",
            defaults={
                "name": "Pharmacy",
                "allowed_product_types": ["medicine", "grocery", "general"],
                "requires_license": True,
                "required_documents": ["mayors_permit", "pharmacy_license"],
            },
        )

    def test_accepts_business_vertical_slug(self):
        serializer = MerchantApplicationSerializer(
            data={
                "business_name": "Sarig Pharmacy",
                "owner_first_name": "Amina",
                "owner_last_name": "Santos",
                "company_email": "pharmacy@example.com",
                "contact_number": "09171234567",
                "business_type": "SHOP",
                "business_vertical_slug": "pharmacy",
                "delivery_time": "ALL_DAY",
                "branch_name": "Main",
                "terms_accepted": True,
                "business_address": "Banggolo, Marawi City",
                "barangay": "Banggolo",
                "city": "Marawi City",
                "province": "Lanao del Sur",
                "postal_code": "9700",
                "location_source": "pin",
                "pinned_address": "Banggolo, Marawi City",
                "latitude": "8.003400",
                "longitude": "124.283900",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertNotIn("business_vertical_slug", serializer.errors)
