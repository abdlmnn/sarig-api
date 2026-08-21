import hashlib
import logging
import threading

from django.conf import settings
from django.db import transaction
from django.utils.module_loading import import_string

from apps.email_templates.services import send_templated_email

from .models import (
    AccountSetupToken,
    ApplicationEditToken,
    MerchantApplication,
    NotificationChannel,
    NotificationEvent,
    OnboardingNotificationDelivery,
    RiderApplication,
)
from .tokens import encode_account_setup_token


logger = logging.getLogger(__name__)
_publish_slots = threading.BoundedSemaphore(2)

EMAIL_TEMPLATES = {
    NotificationEvent.APPLICATION_SUBMITTED: "onboarding.submitted",
    NotificationEvent.MERCHANT_APPROVED: "onboarding.approved.merchant",
    NotificationEvent.RIDER_APPROVED: "onboarding.approved.rider",
    NotificationEvent.APPLICATION_REJECTED: "onboarding.rejected",
    NotificationEvent.CHANGES_REQUESTED: "onboarding.request_changes",
    NotificationEvent.ACCOUNT_ACTIVATED: "onboarding.account_setup_completed",
}


class NotificationNoLongerApplicable(Exception):
    pass


def application_type(application):
    return "MERCHANT" if isinstance(application, MerchantApplication) else "RIDER"


def applicant_email(application):
    return application.company_email if isinstance(application, MerchantApplication) else application.email


def applicant_phone(application):
    return application.contact_number if isinstance(application, MerchantApplication) else application.phone_number


def applicant_name(application):
    return application.applicant_name or applicant_email(application)


def _idempotency_key(event, channel, event_key):
    value = f"{event}:{channel}:{event_key}".encode()
    return hashlib.sha256(value).hexdigest()


def queue_onboarding_event(application, event, event_key, payload=None):
    payload = payload or {}
    app_type = application_type(application)
    deliveries = []
    channel_specs = [(NotificationChannel.EMAIL, applicant_email(application), EMAIL_TEMPLATES[event])]
    if getattr(settings, "ONBOARDING_SMS_BACKEND", ""):
        channel_specs.append((NotificationChannel.SMS, applicant_phone(application), ""))

    for channel, recipient, template_key in channel_specs:
        if not recipient:
            continue
        delivery, created = OnboardingNotificationDelivery.objects.get_or_create(
            idempotency_key=_idempotency_key(event, channel, event_key),
            defaults={
                "event": event,
                "channel": channel,
                "application_id": application.application_id,
                "application_type": app_type,
                "recipient": recipient,
                "template_key": template_key,
                "payload": payload,
            },
        )
        if created:
            deliveries.append(delivery)

    delivery_ids = [str(delivery.pk) for delivery in deliveries]
    if delivery_ids:
        transaction.on_commit(lambda: schedule_deliveries(delivery_ids))
    return deliveries


def schedule_deliveries(delivery_ids):
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        enqueue_deliveries(delivery_ids)
        return
    if not _publish_slots.acquire(blocking=False):
        logger.warning("Onboarding notification publisher is busy; pending deliveries will be recovered by Celery Beat")
        return

    thread = threading.Thread(
        target=_publish_deliveries,
        args=(delivery_ids,),
        daemon=True,
        name="onboarding-notification-publisher",
    )
    thread.start()


def _publish_deliveries(delivery_ids):
    try:
        enqueue_deliveries(delivery_ids)
    finally:
        _publish_slots.release()


def enqueue_deliveries(delivery_ids):
    from .tasks import deliver_onboarding_notification

    for delivery_id in delivery_ids:
        try:
            deliver_onboarding_notification.apply_async(
                args=[delivery_id],
                retry=False,
                ignore_result=True,
            )
        except Exception as exc:
            logger.warning("Failed to queue onboarding notification %s: %s", delivery_id, exc)


def _get_application(delivery):
    model = MerchantApplication if delivery.application_type == "MERCHANT" else RiderApplication
    return model.objects.get(application_id=delivery.application_id)


def _email_context(delivery, application):
    payload = dict(delivery.payload)
    context = {
        "application_id": application.application_id,
        "application_type": delivery.application_type,
        "application_type_label": delivery.application_type.lower(),
        "applicant_name": applicant_name(application),
        **payload,
    }
    frontend_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")

    if delivery.event == NotificationEvent.APPLICATION_SUBMITTED:
        context["status_url"] = f"{frontend_url}/{delivery.application_type.lower()}/status"
    elif delivery.event in (NotificationEvent.MERCHANT_APPROVED, NotificationEvent.RIDER_APPROVED):
        invitation = AccountSetupToken.objects.get(pk=payload["setup_invitation_id"])
        if not invitation.is_active:
            raise NotificationNoLongerApplicable("The setup invitation is no longer active.")
        token = encode_account_setup_token(invitation)
        context["setup_url"] = f"{frontend_url}/accounts/setup/{token}"
    elif delivery.event == NotificationEvent.CHANGES_REQUESTED:
        edit_token = ApplicationEditToken.objects.get(pk=payload["edit_token_id"])
        if not edit_token.is_active:
            raise NotificationNoLongerApplicable("The application edit token is no longer active.")
        context["edit_url"] = f"{frontend_url}/{delivery.application_type.lower()}/application/edit/{edit_token.token}"
        context["requested_fields"] = ", ".join(payload.get("requested_fields", [])) or "None"
    return context


def _sms_message(delivery):
    messages = {
        NotificationEvent.APPLICATION_SUBMITTED: "Sarig received your application. Check your email for details.",
        NotificationEvent.MERCHANT_APPROVED: "Your Sarig merchant application was approved. Check your email to set up your account.",
        NotificationEvent.RIDER_APPROVED: "Your Sarig rider application was approved. Check your email to set up your account.",
        NotificationEvent.APPLICATION_REJECTED: "Your Sarig application status was updated. Check your email for details.",
        NotificationEvent.CHANGES_REQUESTED: "Sarig requested changes to your application. Check your email for instructions.",
        NotificationEvent.ACCOUNT_ACTIVATED: "Your Sarig account is active. You can now sign in.",
    }
    return messages[delivery.event]


def deliver_notification(delivery):
    application = _get_application(delivery)
    if delivery.channel == NotificationChannel.EMAIL:
        sent = send_templated_email(
            delivery.template_key,
            delivery.recipient,
            _email_context(delivery, application),
            fail_silently=False,
        )
        if not sent:
            raise RuntimeError("Email backend did not accept the message.")
        return

    if delivery.channel == NotificationChannel.SMS:
        backend_path = getattr(settings, "ONBOARDING_SMS_BACKEND", "")
        if not backend_path:
            raise NotificationNoLongerApplicable("No SMS backend is configured.")
        backend = import_string(backend_path)
        result = backend(
            recipient=delivery.recipient,
            message=_sms_message(delivery),
            idempotency_key=delivery.idempotency_key,
        )
        if result is False:
            raise RuntimeError("SMS backend did not accept the message.")
        return

    raise NotificationNoLongerApplicable(f"Unsupported notification channel: {delivery.channel}")
