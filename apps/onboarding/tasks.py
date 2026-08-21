import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import NotificationDeliveryStatus, OnboardingNotificationDelivery
from .notifications import NotificationNoLongerApplicable, deliver_notification


logger = logging.getLogger(__name__)
PROCESSING_TIMEOUT = timedelta(minutes=15)
MAX_DELIVERY_ATTEMPTS = 6


@shared_task(bind=True, max_retries=5, acks_late=True, ignore_result=True)
def deliver_onboarding_notification(self, delivery_id):
    stale_before = timezone.now() - PROCESSING_TIMEOUT
    with transaction.atomic():
        delivery = OnboardingNotificationDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status in (
            NotificationDeliveryStatus.SENT,
            NotificationDeliveryStatus.FAILED,
            NotificationDeliveryStatus.SKIPPED,
        ):
            return delivery.status
        if delivery.status == NotificationDeliveryStatus.PROCESSING and delivery.updated_at > stale_before:
            return delivery.status
        delivery.status = NotificationDeliveryStatus.PROCESSING
        delivery.attempt_count += 1
        delivery.next_attempt_at = None
        delivery.save(update_fields=["status", "attempt_count", "next_attempt_at", "updated_at"])

    try:
        deliver_notification(delivery)
    except NotificationNoLongerApplicable as exc:
        delivery.status = NotificationDeliveryStatus.SKIPPED
        delivery.last_error = str(exc)
        delivery.save(update_fields=["status", "last_error", "updated_at"])
        return delivery.status
    except Exception as exc:
        exhausted = delivery.attempt_count >= MAX_DELIVERY_ATTEMPTS
        delivery.status = NotificationDeliveryStatus.FAILED if exhausted else NotificationDeliveryStatus.PENDING
        delivery.last_error = str(exc)[:2000]
        countdown = min(30 * (2 ** max(delivery.attempt_count - 1, 0)), 3600)
        delivery.next_attempt_at = None if exhausted else timezone.now() + timedelta(seconds=countdown)
        delivery.save(update_fields=["status", "last_error", "next_attempt_at", "updated_at"])
        logger.warning(
            "Onboarding notification %s attempt %s failed: %s",
            delivery_id,
            delivery.attempt_count,
            exc,
        )
        if exhausted:
            raise
        raise self.retry(exc=exc, countdown=countdown)

    delivery.status = NotificationDeliveryStatus.SENT
    delivery.sent_at = timezone.now()
    delivery.last_error = ""
    delivery.next_attempt_at = None
    delivery.save(update_fields=["status", "sent_at", "last_error", "next_attempt_at", "updated_at"])
    return delivery.status


@shared_task(ignore_result=True)
def dispatch_pending_onboarding_notifications():
    from .notifications import enqueue_deliveries

    stale_before = timezone.now() - PROCESSING_TIMEOUT
    due_pending = Q(status=NotificationDeliveryStatus.PENDING) & (
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now())
    )
    stale_processing = Q(status=NotificationDeliveryStatus.PROCESSING, updated_at__lte=stale_before)
    delivery_ids = list(
        OnboardingNotificationDelivery.objects.filter(due_pending | stale_processing)
        .order_by("created_at")
        .values_list("pk", flat=True)[:200]
    )
    enqueue_deliveries([str(delivery_id) for delivery_id in delivery_ids])
    return len(delivery_ids)
