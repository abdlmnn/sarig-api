from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient


def upload(name, content_type="application/pdf"):
    return SimpleUploadedFile(name, b"test file", content_type=content_type)


def image_upload(name):
    buffer = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def merchant_payload(**overrides):
    payload = {
        "business_name": "Banggolo Eats",
        "owner_first_name": "Ali",
        "owner_last_name": "Macarambon",
        "company_email": "banggolo.eats@example.com",
        "contact_number": "09171234567",
        "business_type": "RESTAURANT",
        "delivery_time": "ALL_DAY",
        "branch_name": "Main",
        "terms_accepted": "true",
        "business_address": "Banggolo Poblacion, Marawi City, Lanao del Sur, Philippines",
        "barangay": "Banggolo Poblacion",
        "city": "Marawi City",
        "province": "Lanao del Sur",
        "postal_code": "9700",
        "location_source": "pin",
        "pinned_address": "Banggolo Poblacion, Marawi City, Lanao del Sur, Philippines",
        "latitude": "8.003400",
        "longitude": "124.283900",
        "dti_sec_certificate": upload("dti.pdf"),
        "mayors_permit": upload("permit.pdf"),
        "owner_valid_id": image_upload("owner-id.png"),
        "storefront_photo": image_upload("storefront.png"),
    }
    payload.update(overrides)
    return payload


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MerchantSignupLocationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_merchant_apply_accepts_pin_location_without_street(self):
        response = self.client.post(
            "/api/v1/onboarding/merchant/apply/",
            merchant_payload(),
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Merchant application submitted for review.")

    def test_merchant_apply_rejects_pin_outside_marawi(self):
        response = self.client.post(
            "/api/v1/onboarding/merchant/apply/",
            merchant_payload(latitude="14.599500", longitude="120.984200"),
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("coordinates", response.data)

    def test_merchant_apply_rejects_pdf_storefront_photo(self):
        response = self.client.post(
            "/api/v1/onboarding/merchant/apply/",
            merchant_payload(storefront_photo=upload("storefront.pdf")),
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("storefront_photo", response.data)
