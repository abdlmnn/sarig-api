from django.test import TestCase
from apps.users.models import User
from apps.riders.models import RiderProfile
from apps.riders.services import RiderDispatcherService


class RiderDispatcherTests(TestCase):
    def test_haversine_distance_calculation(self):
        distance = RiderDispatcherService.haversine(125.4553, 7.1907, 125.4553, 7.1907)
        self.assertEqual(distance, 0.0)

    def test_rider_assignment_selects_nearest_available_rider(self):
        near_user = User.objects.create_user(username="near", email="near@test.com", password="pw12345")
        far_user = User.objects.create_user(username="far", email="far@test.com", password="pw12345")

        near = RiderProfile.objects.create(
            user=near_user,
            is_online=True,
            is_available=True,
            can_do_delivery=True,
            current_latitude=7.190700,
            current_longitude=125.455300,
        )
        RiderProfile.objects.create(
            user=far_user,
            is_online=True,
            is_available=True,
            can_do_delivery=True,
            current_latitude=7.290700,
            current_longitude=125.555300,
        )

        best, _ = RiderDispatcherService.find_best_rider(7.190700, 125.455300, max_radius_km=20)
        self.assertIsNotNone(best)
        self.assertEqual(best.id, near.id)
