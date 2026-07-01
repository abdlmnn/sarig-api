from django.test import TestCase
from rest_framework.test import APIClient


class MerchantOnboardingOptionsTests(TestCase):
    def test_merchant_options_exposes_order_availability_labels(self):
        response = APIClient().get("/api/v1/onboarding/merchant/options/")

        self.assertEqual(response.status_code, 200)
        delivery_time = response.data["delivery_time"]
        self.assertEqual(delivery_time["field"], "delivery_time")
        self.assertEqual(delivery_time["ui_label"], "Order Availability")
        self.assertEqual(delivery_time["default"], "ALL_DAY")
        self.assertEqual(
            delivery_time["options"],
            [
                {"value": "ALL_DAY", "label": "All day"},
                {"value": "MORNING", "label": "Morning only"},
                {"value": "AFTERNOON", "label": "Afternoon only"},
                {"value": "EVENING", "label": "Evening only"},
            ],
        )
        documents = response.data["documents"]
        self.assertIn({"key": "mayors_permit", "label": "Mayor's Permit / Business Permit"}, documents["base_required"])
        self.assertIn({"key": "pharmacy_license", "label": "Pharmacy License"}, documents["vertical_supported"])
