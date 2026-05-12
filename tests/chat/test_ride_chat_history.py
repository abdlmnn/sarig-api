from django.test import TestCase
from rest_framework.test import APIClient

from apps.riders.models import RiderProfile
from apps.rides.models import Ride, RideStatus, VehicleType
from apps.users.models import Role, User


class RideChatHistoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.passenger = User.objects.create_user("p1", "p1@test.com", "pw12345")
        self.rider_user = User.objects.create_user("r1", "r1@test.com", "pw12345")
        self.other = User.objects.create_user("other", "other@test.com", "pw12345")
        rider_role, _ = Role.objects.get_or_create(name="Rider")
        self.rider_user.roles.add(rider_role)
        self.rider_profile = RiderProfile.objects.create(user=self.rider_user)
        self.ride = Ride.objects.create(
            passenger=self.passenger,
            rider=self.rider_profile,
            requested_vehicle_type=VehicleType.MOTORCYCLE,
            assigned_vehicle_type=VehicleType.MOTORCYCLE,
            pickup_lat=7.1,
            pickup_lng=125.1,
            dropoff_lat=7.2,
            dropoff_lng=125.2,
            status=RideStatus.MATCHED,
        )

    def test_passenger_can_view_ride_chat_history(self):
        self.client.force_authenticate(user=self.passenger)
        res = self.client.get(f"/api/v1/chat/ride-history/{self.ride.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("messages", res.data)
        self.assertEqual(res.data["chat_locked"], False)

    def test_non_participant_cannot_view_ride_chat_history(self):
        self.client.force_authenticate(user=self.other)
        res = self.client.get(f"/api/v1/chat/ride-history/{self.ride.id}/")
        self.assertEqual(res.status_code, 403)

    def test_chat_locked_for_completed_ride(self):
        self.ride.status = RideStatus.COMPLETED
        self.ride.save(update_fields=["status", "updated_at"])
        self.client.force_authenticate(user=self.rider_user)
        res = self.client.get(f"/api/v1/chat/ride-history/{self.ride.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["chat_locked"], True)

