from django.core import mail
from django.test import TestCase, override_settings

from apps.email_templates.models import EmailTemplate
from apps.email_templates.services import render_email, send_templated_email


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailTemplateServiceTests(TestCase):
    def test_default_template_renders_context(self):
        email = render_email(
            "onboarding.rejected",
            {
                "applicant_name": "Amina",
                "application_id": "MR-1001",
                "remarks": "Documents could not be verified.",
            },
        )

        self.assertEqual(email["subject"], "Sarig application rejected")
        self.assertIn("Hi Amina", email["message"])
        self.assertIn("MR-1001", email["message"])
        self.assertIn("Documents could not be verified.", email["message"])
        self.assertIn("Sarig notification", email["html_message"])
        self.assertIn("Documents could not be verified.", email["html_message"])

    def test_submission_template_renders_branded_html_and_plain_text(self):
        email = render_email(
            "onboarding.submitted",
            {
                "applicant_name": "Salih",
                "application_type_label": "merchant",
                "application_id": "MR-TEST123",
                "submitted_at": "2026-08-21 16:26",
                "status_url": "https://merchant.sarig.test/merchant/status",
            },
        )

        self.assertEqual(email["subject"], "We received your Sarig merchant application")
        self.assertIn("We received your application", email["message"])
        self.assertNotIn("Status check:", email["message"])
        self.assertIn("Application received", email["html_message"])
        self.assertIn("View application status", email["html_message"])
        self.assertIn("MR-TEST123", email["html_message"])
        self.assertIn('background:#0a0a0a', email["html_message"])
        self.assertIn('background:#8f1515', email["html_message"])
        self.assertIn('color:#8f1515;font-size:11px', email["html_message"])
        self.assertIn('font-size:24px;font-weight:700', email["html_message"])
        self.assertIn('>sarig<span', email["html_message"])

    def test_database_template_overrides_default_template(self):
        EmailTemplate.objects.create(
            key="onboarding.rejected",
            name="Custom rejection",
            subject="Application {{ application_id }} update",
            body="Hello {{ applicant_name }}. Reason: {{ remarks }}",
        )

        email = render_email(
            "onboarding.rejected",
            {
                "applicant_name": "Amina",
                "application_id": "MR-1001",
                "remarks": "Invalid document.",
            },
        )

        self.assertEqual(email["subject"], "Application MR-1001 update")
        self.assertEqual(email["message"], "Hello Amina. Reason: Invalid document.")

    def test_send_templated_email_uses_rendered_template(self):
        sent = send_templated_email(
            "onboarding.request_changes",
            "applicant@example.com",
            {
                "applicant_name": "Amina",
                "application_id": "MR-1001",
                "remarks": "Upload a clearer ID.",
                "requested_fields": "owner_valid_id",
                "edit_url": "https://sarig.test/edit-token",
            },
        )

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["applicant@example.com"])
        self.assertIn("Upload a clearer ID.", mail.outbox[0].body)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        self.assertEqual(mail.outbox[0].alternatives[0].mimetype, "text/html")
        self.assertIn("Upload a clearer ID.", mail.outbox[0].alternatives[0].content)
