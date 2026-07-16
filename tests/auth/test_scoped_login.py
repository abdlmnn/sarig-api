from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import Role, User


class ScopedLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf_token = self.client.get("/api/v1/auth/csrf/").data["csrf_token"]
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

    def tearDown(self):
        cache.clear()

    def login(self, role, identifier, password):
        return self.client.post(
            f"/api/v1/auth/{role}/login/",
            {"identifier": identifier, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    def test_admin_can_login_with_email(self):
        response = self.login("admin", "admin@sarig.local", "admin12345")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["account_type"], "ADMIN")
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_merchant_can_login_with_username(self):
        response = self.login("merchant", "merchant1", "merchant12345")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["account_type"], "MERCHANT")
        self.assertTrue(response.data["user"]["is_merchant"])

    def test_merchant_cannot_use_admin_scope(self):
        response = self.login("admin", "merchant1@sarig.local", "merchant12345")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "forbidden")

    def test_admin_cannot_use_merchant_scope(self):
        response = self.login("merchant", "superadmin", "admin12345")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "forbidden")

    def test_unknown_identifier_returns_frontend_friendly_error(self):
        response = self.login("admin", "missing@sarig.local", "admin12345")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_credentials")
        self.assertEqual(response.data["message"], "Invalid username/email or password.")

    def test_wrong_password_returns_same_error_as_unknown_identifier(self):
        response = self.login("admin", "admin@sarig.local", "wrong-password")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_credentials")

    def test_legacy_login_rejects_admin_and_merchant_scopes(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "identifier": "admin@sarig.local",
                "password": "admin12345",
                "account_type": "ADMIN",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 410)
