from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.riders.models import RiderProfile
from apps.users.models import Role, User


class RiderLocationUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.rider = User.objects.create_user(
            username="location-rider",
            email="location-rider@test.com",
            password="pw12345",
        )
        rider_role, _ = Role.objects.get_or_create(name="Rider")
        self.rider.roles.add(rider_role)
        self.profile = RiderProfile.objects.create(user=self.rider)
        self.client.force_authenticate(user=self.rider)

    def test_location_update_persists_normalized_coordinates(self):
        response = self.client.post(
            "/api/v1/riders/location/update/",
            {"latitude": "7.19070049", "longitude": "125.45530051"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_latitude, Decimal("7.190700"))
        self.assertEqual(self.profile.current_longitude, Decimal("125.455301"))
        self.assertEqual(response.data["location"]["latitude"], "7.190700")
        self.assertEqual(response.data["location"]["longitude"], "125.455301")
        self.assertIsNotNone(response.data["location"]["last_updated_at"])

    def test_location_update_rejects_invalid_coordinates(self):
        invalid_locations = [
            {"latitude": "91", "longitude": "125.4553"},
            {"latitude": "7.19", "longitude": "181"},
            {"latitude": "invalid", "longitude": "125.4553"},
            {"latitude": "", "longitude": "125.4553"},
        ]

        for location in invalid_locations:
            with self.subTest(location=location):
                response = self.client.post(
                    "/api/v1/riders/location/update/",
                    location,
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.current_latitude)
        self.assertIsNone(self.profile.current_longitude)

    def test_location_update_requires_rider_role(self):
        customer = User.objects.create_user(
            username="location-customer",
            email="location-customer@test.com",
            password="pw12345",
        )
        RiderProfile.objects.create(user=customer)
        self.client.force_authenticate(user=customer)

        response = self.client.post(
            "/api/v1/riders/location/update/",
            {"latitude": "7.19", "longitude": "125.4553"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
