from django.core import mail
from django.test import TestCase, override_settings

from apps.email_templates.models import EmailTemplate
from apps.onboarding.models import ApplicationStatus, MerchantApplication, RiderApplication
from apps.onboarding.services import ApplicationService


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class OnboardingEmailTemplateTests(TestCase):
    def test_approval_email_uses_email_template_app(self):
        EmailTemplate.objects.create(
            key="onboarding.approved.merchant",
            name="Custom merchant approval",
            subject="Approved {{ application_id }}",
            body="Setup link: {{ setup_url }}",
        )
        application = MerchantApplication.objects.create(
            business_name="Sultan Food House",
            owner_first_name="Hassan",
            owner_last_name="Macarambon",
            company_email="merchant@example.com",
            contact_number="+63 917 420 1188",
            business_type="RESTAURANT",
            delivery_time="ALL_DAY",
            branch_name="Main",
            terms_accepted=True,
            business_address="Amai Pakpak Avenue",
            barangay="Banggolo",
            city="Marawi",
            province="Lanao del Sur",
            postal_code="9700",
            latitude="8.003400",
            longitude="124.283900",
            status=ApplicationStatus.PENDING,
        )

        with self.captureOnCommitCallbacks(execute=True):
            ApplicationService.approve_merchant(application)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, f"Approved {application.application_id}")
        self.assertIn("/accounts/setup/", mail.outbox[0].body)

    def test_request_changes_email_uses_email_template_app(self):
        application = RiderApplication.objects.create(
            first_name="Ameer",
            last_name="S.",
            email="rider@example.com",
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
            status=ApplicationStatus.PENDING,
        )

        with self.captureOnCommitCallbacks(execute=True):
            ApplicationService.request_changes(
                application,
                "Please upload a clearer license.",
                ["professional_drivers_license"],
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Sarig application changes requested")
        self.assertIn("Please upload a clearer license.", mail.outbox[0].body)
        self.assertIn("professional_drivers_license", mail.outbox[0].body)
