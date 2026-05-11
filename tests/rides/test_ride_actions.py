from django.test import TestCase
from rest_framework.test import APIClient

from apps.riders.models import RiderProfile
from apps.rides.models import Ride, RideStatus, VehicleType
from apps.users.models import Role, User


class RideActionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.passenger = User.objects.create_user("passenger", "passenger@test.com", "pw12345")
        self.rider_user = User.objects.create_user("rider", "rider@test.com", "pw12345")
        rider_role, _ = Role.objects.get_or_create(name="Rider")
        self.rider_user.roles.add(rider_role)
        self.rider_profile = RiderProfile.objects.create(user=self.rider_user)
        self.admin = User.objects.create_superuser("admin", "admin@test.com", "pw12345")

        self.ride = Ride.objects.create(
            passenger=self.passenger,
            requested_vehicle_type=VehicleType.MOTORCYCLE,
            pickup_lat=7.123456,
            pickup_lng=125.123456,
            dropoff_lat=7.223456,
            dropoff_lng=125.223456,
            estimated_fare=100,
        )

    def test_passenger_can_cancel_requested_ride(self):
        self.client.force_authenticate(user=self.passenger)
        res = self.client.post(f"/api/v1/rides/{self.ride.id}/cancel/")
        self.assertEqual(res.status_code, 200)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, RideStatus.CANCELLED)
        self.assertEqual(self.ride.cancelled_by_id, self.passenger.id)

    def test_non_assigned_rider_cannot_arrive(self):
        self.client.force_authenticate(user=self.rider_user)
        res = self.client.post(f"/api/v1/rides/{self.ride.id}/arrive/")
        self.assertEqual(res.status_code, 404)

    def test_admin_can_accept_and_assigned_rider_can_progress(self):
        self.ride.rider = self.rider_profile
        self.ride.save(update_fields=["rider", "updated_at"])

        self.client.force_authenticate(user=self.admin)
        accept_res = self.client.post(f"/api/v1/rides/{self.ride.id}/accept/")
        self.assertEqual(accept_res.status_code, 200)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, RideStatus.MATCHED)
        self.assertIsNotNone(self.ride.matched_at)

        self.client.force_authenticate(user=self.rider_user)
        arrive_res = self.client.post(f"/api/v1/rides/{self.ride.id}/arrive/")
        self.assertEqual(arrive_res.status_code, 200)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, RideStatus.RIDER_ARRIVED)

        start_res = self.client.post(f"/api/v1/rides/{self.ride.id}/start/")
        self.assertEqual(start_res.status_code, 200)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, RideStatus.IN_TRIP)
        self.assertIsNotNone(self.ride.started_at)

        complete_res = self.client.post(f"/api/v1/rides/{self.ride.id}/complete/")
        self.assertEqual(complete_res.status_code, 200)
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.status, RideStatus.COMPLETED)
        self.assertIsNotNone(self.ride.completed_at)
