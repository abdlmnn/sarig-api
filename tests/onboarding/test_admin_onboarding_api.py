from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import resolve
from django.urls.exceptions import Resolver404
from rest_framework.test import APIClient

from apps.onboarding.models import ApplicationStatus, MerchantApplication, RiderApplication


def upload(name, content_type="application/pdf"):
    return SimpleUploadedFile(name, b"test file", content_type=content_type)


class AdminOnboardingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )
        self.client.force_authenticate(self.admin)
        self.merchant = MerchantApplication.objects.create(
            business_name="Sultan Food House",
            owner_first_name="Hassan",
            owner_last_name="Macarambon",
            company_email="sultan.food@example.com",
            contact_number="+63 917 420 1188",
            business_type="RESTAURANT",
            delivery_time="ALL_DAY",
            branch_name="Main",
            terms_accepted=True,
            business_address="Amai Pakpak Avenue",
            street="Amai Pakpak Avenue",
            barangay="Banggolo",
            city="Marawi",
            province="Lanao del Sur",
            postal_code="9700",
            latitude="8.003400",
            longitude="124.283900",
            dti_sec_certificate=upload("Sultan-Food-DTI.pdf"),
            mayors_permit=upload("Sultan-Food-Mayors-Permit.pdf"),
            owner_valid_id=upload("Hassan-ID.pdf"),
            storefront_photo=upload("Storefront.jpg", "image/jpeg"),
            status=ApplicationStatus.PENDING,
        )
        self.rider = RiderApplication.objects.create(
            first_name="Ameer",
            last_name="S.",
            email="ameer.rider@example.com",
            phone_number="+63 906 218 0441",
            terms_accepted=True,
            current_address="Saduc, Marawi City",
            barangay="Saduc",
            city="Marawi",
            province="Lanao del Sur",
            postal_code="9700",
            emergency_contact_name="Omar S.",
            emergency_contact_number="+63 915 222 1180",
            emergency_contact_relationship="Brother",
            vehicle_type="MOTORCYCLE",
            vehicle_brand="Honda Click",
            plate_number="MAW 2184",
            vehicle_photo_front=upload("Vehicle-Front.jpg", "image/jpeg"),
            vehicle_photo_back=upload("Vehicle-Back.jpg", "image/jpeg"),
            professional_drivers_license=upload("Drivers-License.pdf"),
            nbi_clearance=upload("NBI-Clearance.pdf"),
            status=ApplicationStatus.REQUEST_CHANGES,
        )

    def test_application_list_includes_frontend_fields_and_totals(self):
        response = self.client.get("/api/v1/admin/onboarding/applications/?type=all&status=all&page=1&page_size=20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["totals"]["merchants"], 1)
        self.assertEqual(response.data["totals"]["riders"], 1)
        self.assertEqual(response.data["totals"]["ready"], 1)
        self.assertEqual(response.data["totals"]["changes"], 1)
        item = next(item for item in response.data["results"] if item["application_id"] == self.merchant.application_id)
        self.assertEqual(item["type"], "MERCHANT")
        self.assertEqual(item["applicant_name"], "Hassan Macarambon")
        self.assertEqual(item["business_name"], "Sultan Food House")
        self.assertEqual(item["barangay"], "Banggolo")
        self.assertEqual(item["city"], "Marawi City")

    def test_merchant_detail_is_flat_and_includes_documents(self):
        response = self.client.get(f"/api/v1/admin/onboarding/applications/{self.merchant.application_id}/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("data", response.data)
        self.assertEqual(response.data["business_name"], "Sultan Food House")
        self.assertEqual(response.data["owner_first_name"], "Hassan")
        self.assertEqual(response.data["business_type"], "Restaurant")
        self.assertEqual(response.data["delivery_time"], "allday")
        self.assertEqual(response.data["city"], "Marawi City")
        document = next(item for item in response.data["documents"] if item["key"] == "dti_sec_certificate")
        self.assertEqual(document["label"], "DTI / SEC Certificate")
        self.assertEqual(document["file_type"], "application/pdf")
        self.assertTrue(document["required"])
        self.assertEqual(
            document["view_url"],
            f"/api/v1/admin/onboarding/applications/{self.merchant.application_id}/documents/dti_sec_certificate/",
        )

    def test_rider_detail_is_flat_and_includes_documents(self):
        response = self.client.get(f"/api/v1/admin/onboarding/applications/{self.rider.application_id}/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("data", response.data)
        self.assertEqual(response.data["first_name"], "Ameer")
        self.assertEqual(response.data["vehicle_type"], "MOTORCYCLE")
        self.assertEqual(response.data["emergency_contact_relationship"], "Brother")
        document = next(item for item in response.data["documents"] if item["key"] == "nbi_clearance")
        self.assertEqual(document["label"], "NBI Clearance")
        self.assertEqual(document["file_type"], "application/pdf")
        self.assertTrue(document["required"])

    def test_pdf_document_endpoint_returns_pdf_content_type(self):
        response = self.client.get(
            f"/api/v1/admin/onboarding/applications/{self.merchant.application_id}/documents/dti_sec_certificate/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertIn(".pdf", response["Content-Disposition"])

    def test_actions_return_frontend_messages(self):
        approve_response = self.client.post(f"/api/v1/admin/onboarding/applications/{self.merchant.application_id}/approve/")
        changes_response = self.client.post(
            f"/api/v1/admin/onboarding/applications/{self.rider.application_id}/request-changes/",
            {"admin_remarks": "Please upload clearer documents.", "requested_fields": ["nbi_clearance"]},
            format="json",
        )
        reject_response = self.client.post(
            f"/api/v1/admin/onboarding/applications/{self.rider.application_id}/reject/",
            {"admin_remarks": "Documents could not be verified."},
            format="json",
        )

        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["message"], "Application approved.")
        self.assertEqual(changes_response.status_code, 200)
        self.assertEqual(changes_response.data["message"], "Change request sent.")
        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.data["message"], "Application rejected.")

    def test_development_media_url_is_registered(self):
        try:
            match = resolve("/media/onboarding/merchants/bir_cor/example.pdf")
        except Resolver404:
            match = None

        if settings.DEBUG:
            self.assertIsNotNone(match)
            self.assertEqual(match.url_name, "django.views.static.serve")
        else:
            self.assertIsNone(match)
