from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import Role, User


class ScopedLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")

        self.admin = User.objects.create_superuser(
            username="superadmin",
            email="admin@sarig.local",
            password="admin12345",
        )
        self.merchant = User.objects.create_user(
            username="merchant1",
            email="merchant1@sarig.local",
            password="merchant12345",
        )
        self.merchant.roles.add(merchant_role)

    def test_admin_can_login_with_email(self):
        response = self.client.post(
            "/api/v1/auth/admin/login/",
            {"identifier": "admin@sarig.local", "password": "admin12345"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["account_type"], "ADMIN")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_merchant_can_login_with_username(self):
        response = self.client.post(
            "/api/v1/auth/merchant/login/",
            {"identifier": "merchant1", "password": "merchant12345"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["account_type"], "MERCHANT")
        self.assertTrue(response.data["user"]["is_merchant"])

    def test_merchant_cannot_use_admin_login(self):
        response = self.client.post(
            "/api/v1/auth/admin/login/",
            {"identifier": "merchant1@sarig.local", "password": "merchant12345"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "forbidden")

    def test_admin_cannot_use_merchant_login(self):
        response = self.client.post(
            "/api/v1/auth/merchant/login/",
            {"identifier": "superadmin", "password": "admin12345"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "forbidden")

    def test_unknown_identifier_returns_frontend_friendly_error(self):
        response = self.client.post(
            "/api/v1/auth/admin/login/",
            {"identifier": "missing@sarig.local", "password": "admin12345"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_credentials")
        self.assertEqual(response.data["message"], "Invalid username/email or password.")

    def test_wrong_password_returns_same_error_as_unknown_identifier(self):
        response = self.client.post(
            "/api/v1/auth/admin/login/",
            {"identifier": "admin@sarig.local", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_credentials")
        self.assertEqual(response.data["message"], "Invalid username/email or password.")
