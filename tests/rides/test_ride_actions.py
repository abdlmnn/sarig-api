from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.riders.models import RiderProfile
from apps.rides.models import FareBreakdown
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
        self.ride.rider = self.rider_profile
        self.ride.status = RideStatus.MATCHED
        self.ride.save(update_fields=["rider", "status", "updated_at"])
        self.rider_profile.is_available = False
        self.rider_profile.save(update_fields=["is_available"])
        self.client.force_authenticate(user=self.passenger)
        res = self.client.post(
            f"/api/v1/rides/{self.ride.id}/cancel/",
            {"cancel_reason": "Passenger changed plans"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.ride.refresh_from_db()
        self.rider_profile.refresh_from_db()
        self.assertEqual(self.ride.status, RideStatus.CANCELLED)
        self.assertEqual(self.ride.cancelled_by_id, self.passenger.id)
        self.assertEqual(self.ride.cancel_reason, "Passenger changed plans")
        self.assertTrue(self.rider_profile.is_available)

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

    def test_admin_can_assign_eligible_rider(self):
        self.rider_profile.is_online = True
        self.rider_profile.is_available = True
        self.rider_profile.can_do_ride_hailing = True
        self.rider_profile.vehicle_type = VehicleType.MOTORCYCLE
        self.rider_profile.save()

        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            f"/api/v1/rides/{self.ride.id}/assign/",
            {"rider_id": str(self.rider_profile.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.ride.refresh_from_db()
        self.rider_profile.refresh_from_db()
        self.assertEqual(self.ride.status, RideStatus.MATCHED)
        self.assertEqual(self.ride.rider_id, self.rider_profile.id)
        self.assertEqual(self.ride.assigned_vehicle_type, VehicleType.MOTORCYCLE)
        self.assertFalse(self.rider_profile.is_available)

    def test_assign_rejects_vehicle_mismatch(self):
        self.rider_profile.is_online = True
        self.rider_profile.is_available = True
        self.rider_profile.can_do_ride_hailing = True
        self.rider_profile.vehicle_type = VehicleType.CAR
        self.rider_profile.save()

        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            f"/api/v1/rides/{self.ride.id}/assign/",
            {"rider_id": str(self.rider_profile.id)},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_assign_is_idempotent_for_same_rider(self):
        self.rider_profile.is_online = True
        self.rider_profile.is_available = True
        self.rider_profile.can_do_ride_hailing = True
        self.rider_profile.vehicle_type = VehicleType.MOTORCYCLE
        self.rider_profile.save()
        self.client.force_authenticate(user=self.admin)

        first = self.client.post(
            f"/api/v1/rides/{self.ride.id}/assign/",
            {"rider_id": str(self.rider_profile.id)},
            format="json",
        )
        second = self.client.post(
            f"/api/v1/rides/{self.ride.id}/assign/",
            {"rider_id": str(self.rider_profile.id)},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

    def test_create_ride_generates_estimated_fare_breakdown(self):
        self.client.force_authenticate(user=self.passenger)
        res = self.client.post(
            "/api/v1/rides/",
            {
                "requested_vehicle_type": VehicleType.MOTORCYCLE,
                "pickup_lat": "7.100000",
                "pickup_lng": "125.100000",
                "dropoff_lat": "7.200000",
                "dropoff_lng": "125.200000",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        ride = Ride.objects.get(id=res.data["id"])
        self.assertGreater(ride.estimated_fare, 0)
        self.assertTrue(FareBreakdown.objects.filter(ride=ride).exists())

    def test_complete_sets_final_fare(self):
        self.rider_profile.is_online = True
        self.rider_profile.is_available = True
        self.rider_profile.can_do_ride_hailing = True
        self.rider_profile.vehicle_type = VehicleType.MOTORCYCLE
        self.rider_profile.save()
        self.client.force_authenticate(user=self.admin)
        self.client.post(f"/api/v1/rides/{self.ride.id}/assign/", {"rider_id": str(self.rider_profile.id)}, format="json")
        self.client.force_authenticate(user=self.rider_user)
        self.client.post(f"/api/v1/rides/{self.ride.id}/arrive/")
        self.client.post(f"/api/v1/rides/{self.ride.id}/start/")
        self.ride.distance_km = 5
        self.ride.duration_min = 18
        self.ride.save(update_fields=["distance_km", "duration_min", "updated_at"])
        complete_res = self.client.post(f"/api/v1/rides/{self.ride.id}/complete/")
        self.assertEqual(complete_res.status_code, 200)
        self.ride.refresh_from_db()
        self.rider_profile.refresh_from_db()
        self.assertIsNotNone(self.ride.final_fare)
        self.assertGreater(self.ride.final_fare, 0)
        self.assertTrue(self.rider_profile.is_available)

    @override_settings(JOYRIDE_ENABLE_AUTO_MATCHING=True, JOYRIDE_MATCHING_MAX_RADIUS_KM=10)
    def test_create_ride_auto_assigns_nearest_eligible_rider(self):
        self.rider_profile.is_online = True
        self.rider_profile.is_available = True
        self.rider_profile.can_do_ride_hailing = True
        self.rider_profile.vehicle_type = VehicleType.MOTORCYCLE
        self.rider_profile.current_latitude = "7.100100"
        self.rider_profile.current_longitude = "125.100100"
        self.rider_profile.save()

        self.client.force_authenticate(user=self.passenger)
        res = self.client.post(
            "/api/v1/rides/",
            {
                "requested_vehicle_type": VehicleType.MOTORCYCLE,
                "pickup_lat": "7.100000",
                "pickup_lng": "125.100000",
                "dropoff_lat": "7.200000",
                "dropoff_lng": "125.200000",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        ride = Ride.objects.get(id=res.data["id"])
        self.rider_profile.refresh_from_db()
        self.assertEqual(ride.status, RideStatus.MATCHED)
        self.assertEqual(ride.rider_id, self.rider_profile.id)
        self.assertFalse(self.rider_profile.is_available)

    @override_settings(JOYRIDE_ENABLE_AUTO_MATCHING=True, JOYRIDE_MATCHING_MAX_RADIUS_KM=1)
    def test_create_ride_auto_matching_no_candidate_keeps_requested(self):
        self.rider_profile.is_online = True
        self.rider_profile.is_available = True
        self.rider_profile.can_do_ride_hailing = True
        self.rider_profile.vehicle_type = VehicleType.MOTORCYCLE
        self.rider_profile.current_latitude = "8.000000"
        self.rider_profile.current_longitude = "126.000000"
        self.rider_profile.save()

        self.client.force_authenticate(user=self.passenger)
        res = self.client.post(
            "/api/v1/rides/",
            {
                "requested_vehicle_type": VehicleType.MOTORCYCLE,
                "pickup_lat": "7.100000",
                "pickup_lng": "125.100000",
                "dropoff_lat": "7.200000",
                "dropoff_lng": "125.200000",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        ride = Ride.objects.get(id=res.data["id"])
        self.assertEqual(ride.status, RideStatus.REQUESTED)
        self.assertIsNone(ride.rider_id)
