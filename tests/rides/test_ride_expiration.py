from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.rides.models import Ride, RideStatus, VehicleType
from apps.users.models import User


@override_settings(JOYRIDE_REQUEST_TIMEOUT_MINUTES=5)
class RideExpirationCommandTests(TestCase):
    def setUp(self):
        self.passenger = User.objects.create_user("passenger2", "passenger2@test.com", "pw12345")

    def _create_ride(self, status=RideStatus.REQUESTED):
        return Ride.objects.create(
            passenger=self.passenger,
            requested_vehicle_type=VehicleType.MOTORCYCLE,
            pickup_lat=7.100000,
            pickup_lng=125.100000,
            dropoff_lat=7.200000,
            dropoff_lng=125.200000,
            status=status,
        )

    def test_expires_only_stale_requested_rides(self):
        stale = self._create_ride(status=RideStatus.REQUESTED)
        fresh = self._create_ride(status=RideStatus.REQUESTED)
        matched = self._create_ride(status=RideStatus.MATCHED)

        stale.requested_at = timezone.now() - timedelta(minutes=10)
        stale.save(update_fields=["requested_at"])
        fresh.requested_at = timezone.now() - timedelta(minutes=2)
        fresh.save(update_fields=["requested_at"])

        call_command("expire_pending_rides")

        stale.refresh_from_db()
        fresh.refresh_from_db()
        matched.refresh_from_db()

        self.assertEqual(stale.status, RideStatus.EXPIRED)
        self.assertEqual(fresh.status, RideStatus.REQUESTED)
        self.assertEqual(matched.status, RideStatus.MATCHED)

