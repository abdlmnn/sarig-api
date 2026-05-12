from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.rides.models import Ride, RideEvent, RideStatus


class Command(BaseCommand):
    help = "Expires stale REQUESTED rides that were not matched within the timeout window."

    def handle(self, *args, **options):
        timeout_minutes = settings.JOYRIDE_REQUEST_TIMEOUT_MINUTES
        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)
        stale_rides = Ride.objects.filter(
            status=RideStatus.REQUESTED,
            requested_at__lt=cutoff,
        )
        count = 0
        for ride in stale_rides:
            ride.transition_to(RideStatus.EXPIRED)
            ride.save(update_fields=["status", "updated_at"])
            RideEvent.objects.create(
                ride=ride,
                event_type="STATUS_EXPIRED",
                actor=None,
                payload={"status": RideStatus.EXPIRED, "reason": "request_timeout"},
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Expired rides: {count}"))

