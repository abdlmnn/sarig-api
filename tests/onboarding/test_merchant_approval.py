from decimal import Decimal

from django.test import TestCase

from apps.onboarding.models import AccountSetupToken, ApplicationStatus, BusinessType, DeliveryTime, MerchantApplication
from apps.onboarding.services import ApplicationService
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store


class MerchantApprovalTests(TestCase):
    def test_store_and_role_are_created_only_after_account_setup(self):
        application = MerchantApplication.objects.create(
            business_name="Sarig Kitchen",
            owner_first_name="Abdul",
            owner_last_name="Owner",
            company_email="store@example.com",
            contact_number="09123456789",
            business_type=BusinessType.RESTAURANT,
            delivery_time=DeliveryTime.ALL_DAY,
            branch_name="Main Branch",
            business_address="123 Test Street, Marawi City",
            city="Marawi",
            barangay="Datu Saber",
            province="Lanao del Sur",
            postal_code="9700",
            street="123 Test Street",
            pinned_address="123 Test Street, Marawi, Lanao del Sur",
            latitude=Decimal("7.190700"),
            longitude=Decimal("125.455300"),
            dti_sec_certificate="onboarding/merchants/dti_sec/test.pdf",
            mayors_permit="onboarding/merchants/mayors_permit/test.pdf",
            owner_valid_id="onboarding/merchants/ids/test.pdf",
            storefront_photo="onboarding/merchants/photos/test.jpg",
        )

        setup_token = ApplicationService.approve_merchant(application)

        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.APPROVED)
        self.assertIsNone(application.applicant)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Store.objects.count(), 0)
        self.assertFalse(Role.objects.filter(name="Merchant").exists())
        self.assertIsInstance(setup_token, AccountSetupToken)

        applicant = ApplicationService.complete_account_setup(setup_token, "StrongMerchantPassword!42")
        application.refresh_from_db()
        applicant.refresh_from_db()
        store = Store.objects.get(owner=applicant)
        self.assertEqual(store.owner, applicant)
        self.assertEqual(store.name, "Sarig Kitchen")
        self.assertEqual(store.vertical.name, "Restaurant")
        self.assertEqual(store.branch_name, "Main Branch")
        self.assertEqual(store.company_email, "store@example.com")
        self.assertEqual(store.contact_number, "+639123456789")
        self.assertEqual(store.delivery_time, DeliveryTime.ALL_DAY)
        self.assertEqual(store.city, "Marawi")
        self.assertEqual(store.barangay, "Datu Saber")
        self.assertEqual(store.province, "Lanao del Sur")
        self.assertEqual(store.postal_code, "9700")
        self.assertEqual(store.street_address, "123 Test Street, Marawi, Lanao del Sur")
        self.assertEqual(store.latitude, Decimal("7.190700"))
        self.assertEqual(store.longitude, Decimal("125.455300"))
        self.assertEqual(store.location_wkt, "POINT(125.4553 7.1907)")
        self.assertEqual(application.status, ApplicationStatus.ACTIVE)
        self.assertEqual(applicant.email, "store@example.com")
        self.assertTrue(applicant.is_active)
        self.assertTrue(applicant.roles.filter(name="Merchant").exists())
        self.assertTrue(Role.objects.filter(name="Merchant").exists())
        self.assertTrue(BusinessVertical.objects.filter(slug="restaurant").exists())
        setup_token.refresh_from_db()
        self.assertIsNotNone(setup_token.used_at)
