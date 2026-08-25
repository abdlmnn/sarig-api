from unittest.mock import patch

from celery.exceptions import Retry
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.onboarding.models import (
    AccountSetupToken,
    ApplicationStatus,
    MerchantApplication,
    NotificationDeliveryStatus,
    NotificationEvent,
    OnboardingNotificationDelivery,
)
from apps.onboarding.services import ApplicationService
from apps.onboarding.tasks import deliver_onboarding_notification
from apps.onboarding.tokens import encode_account_setup_token
from apps.users.models import User
from apps.vendors.models import Store


sms_calls = []


def fake_sms_backend(**kwargs):
    sms_calls.append(kwargs)
    return True


def merchant_application(**overrides):
    values = {
        "business_name": "Sarig Kitchen",
        "owner_first_name": "Amina",
        "owner_last_name": "Santos",
        "company_email": "merchant@example.com",
        "contact_number": "09171234567",
        "business_type": "RESTAURANT",
        "delivery_time": "ALL_DAY",
        "branch_name": "Main",
        "terms_accepted": True,
        "business_address": "Amai Pakpak Avenue",
        "barangay": "Banggolo",
        "city": "Marawi",
        "province": "Lanao del Sur",
        "postal_code": "9700",
        "latitude": "8.003400",
        "longitude": "124.283900",
        "status": ApplicationStatus.PENDING,
    }
    values.update(overrides)
    return MerchantApplication.objects.create(**values)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class MerchantAccountSetupTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signed_invitation_activates_email_login_once(self):
        application = merchant_application()
        with self.captureOnCommitCallbacks(execute=True):
            invitation = ApplicationService.approve_merchant(application)

        invitation.refresh_from_db()
        self.assertIsNone(invitation.token)
        self.assertEqual(len(mail.outbox), 1)
        signed_token = encode_account_setup_token(invitation)

        response = self.client.post(
            f"/api/v1/onboarding/accounts/setup/{signed_token}/",
            {
                "password": "StrongMerchantPassword!42",
                "password_confirm": "StrongMerchantPassword!42",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        application.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.ACTIVE)
        self.assertIsNotNone(invitation.used_at)
        user = User.objects.get(email="merchant@example.com")
        self.assertTrue(user.roles.filter(name="Merchant").exists())
        self.assertTrue(Store.objects.filter(owner=user, is_active=True).exists())

        login_response = self.client.post(
            "/api/v1/auth/merchant/login/",
            {"identifier": "merchant@example.com", "password": "StrongMerchantPassword!42"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)

        reused_response = self.client.post(
            f"/api/v1/onboarding/accounts/setup/{signed_token}/",
            {
                "password": "AnotherStrongPassword!42",
                "password_confirm": "AnotherStrongPassword!42",
            },
            format="json",
        )
        self.assertEqual(reused_response.status_code, 400)

    def test_duplicate_approval_is_idempotent(self):
        application = merchant_application()
        first = ApplicationService.approve_merchant(application)
        second = ApplicationService.approve_merchant(application)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(AccountSetupToken.objects.filter(application_id=application.application_id).count(), 1)
        self.assertEqual(
            OnboardingNotificationDelivery.objects.filter(event=NotificationEvent.MERCHANT_APPROVED).count(),
            1,
        )

    def test_reissue_revokes_the_previous_invitation(self):
        application = merchant_application()
        first = ApplicationService.approve_merchant(application)
        second = ApplicationService.reissue_setup_invitation(application)

        first.refresh_from_db()
        self.assertIsNotNone(first.revoked_at)
        self.assertTrue(second.is_active)
        self.assertFalse(first.is_active)

    def test_notification_delivery_is_persisted_and_marked_sent(self):
        application = merchant_application()
        with self.captureOnCommitCallbacks(execute=True):
            ApplicationService.approve_merchant(application)

        delivery = OnboardingNotificationDelivery.objects.get(event=NotificationEvent.MERCHANT_APPROVED)
        self.assertEqual(delivery.status, NotificationDeliveryStatus.SENT)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.sent_at)

    def test_temporary_delivery_failure_records_attempt_and_retries(self):
        application = merchant_application()
        ApplicationService.approve_merchant(application)
        delivery = OnboardingNotificationDelivery.objects.get(event=NotificationEvent.MERCHANT_APPROVED)

        with patch("apps.onboarding.tasks.deliver_notification", side_effect=OSError("provider unavailable")):
            with patch.object(deliver_onboarding_notification, "retry", side_effect=Retry()) as retry:
                with self.assertRaises(Retry):
                    deliver_onboarding_notification.run(str(delivery.pk))

        delivery.refresh_from_db()
        retry.assert_called_once()
        self.assertEqual(delivery.status, NotificationDeliveryStatus.PENDING)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.next_attempt_at)
        self.assertIn("provider unavailable", delivery.last_error)

    @override_settings(
        ONBOARDING_SMS_BACKEND="tests.onboarding.test_merchant_account_setup.fake_sms_backend",
    )
    def test_configured_sms_backend_uses_the_same_business_event(self):
        sms_calls.clear()
        application = merchant_application()
        with self.captureOnCommitCallbacks(execute=True):
            ApplicationService.approve_merchant(application)

        self.assertEqual(len(sms_calls), 1)
        self.assertEqual(sms_calls[0]["recipient"], "09171234567")
        self.assertIn("approved", sms_calls[0]["message"])
        self.assertEqual(
            OnboardingNotificationDelivery.objects.filter(event=NotificationEvent.MERCHANT_APPROVED).count(),
            2,
        )

    def test_requested_document_can_be_resubmitted_without_terms_field(self):
        application = merchant_application()
        edit_token = ApplicationService.request_changes(
            application,
            "Upload a corrected permit.",
            ["branch_name"],
        )

        response = self.client.patch(
            f"/api/v1/onboarding/applications/edit/{edit_token.token}/",
            {"branch_name": "Updated Branch"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        edit_token.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.PENDING)
        self.assertEqual(application.branch_name, "Updated Branch")
        self.assertIsNotNone(edit_token.revoked_at)

    def test_rejection_revokes_an_existing_edit_token(self):
        application = merchant_application()
        edit_token = ApplicationService.request_changes(application, "Update the branch.", ["branch_name"])

        ApplicationService.reject_application(application, "Unable to verify the business.")

        application.refresh_from_db()
        edit_token.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.REJECTED)
        self.assertFalse(edit_token.is_active)

    def test_change_request_reissue_replaces_the_edit_token(self):
        application = merchant_application()
        first = ApplicationService.request_changes(application, "Update the branch.", ["branch_name"])

        second = ApplicationService.reissue_change_request(application)

        first.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
        self.assertNotEqual(first.pk, second.pk)
