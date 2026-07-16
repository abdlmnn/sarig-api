from django.test import TestCase
from rest_framework.test import APIClient

from apps.riders.models import RiderProfile
from apps.users.models import User


class AdminRiderActionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin-riders",
            email="admin-riders@example.com",
            password="password123",
        )
        self.user = User.objects.create_user(
            username="rider-operations",
            email="rider-operations@example.com",
            password="password123",
        )
        self.rider = RiderProfile.objects.create(
            user=self.user,
            is_online=True,
            is_available=True,
            vehicle_type="MOTORCYCLE",
        )
        self.url = f"/api/v1/operations/riders/{self.rider.id}/action"

    def act(self, action, reason="Reviewed by operations"):
        return self.client.patch(
            self.url,
            {"action": action, "reason": reason},
            format="json",
        )

    def test_admin_can_suspend_and_reactivate_rider(self):
        self.client.force_authenticate(self.admin)

        suspended = self.act("SUSPEND_ACCOUNT")
        self.assertEqual(suspended.status_code, 200)
        self.user.refresh_from_db()
        self.rider.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.rider.is_online)
        self.assertFalse(self.rider.is_available)

        reactivated = self.act("REACTIVATE_ACCOUNT")
        self.assertEqual(reactivated.status_code, 200)
        self.user.refresh_from_db()
        self.rider.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.rider.is_online)
        self.assertTrue(self.rider.is_available)

    def test_action_requires_reason(self):
        self.client.force_authenticate(self.admin)

        response = self.act("SUSPEND_ACCOUNT", "")

        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.data)

    def test_non_admin_cannot_manage_rider(self):
        self.client.force_authenticate(self.user)

        self.assertEqual(self.act("SUSPEND_ACCOUNT").status_code, 403)
