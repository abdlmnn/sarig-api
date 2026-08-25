from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.riders.models import RiderProfile
from apps.users.models import Role, User


class RiderMobileLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        rider_role, _ = Role.objects.get_or_create(name="Rider")
        customer_role, _ = Role.objects.get_or_create(name="Customer")
        self.rider = User.objects.create_user(
            username="mobile-rider",
            email="mobile-rider@sarig.local",
            password="rider-password-123",
        )
        self.rider.roles.add(rider_role)
        RiderProfile.objects.create(user=self.rider, is_online=True)
        self.customer = User.objects.create_user(
            username="mobile-customer",
            email="mobile-customer@sarig.local",
            password="customer-password-123",
        )
        self.customer.roles.add(customer_role)
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def login(self, identifier, password):
        return self.client.post(
            "/api/v1/auth/login/",
            {
                "identifier": identifier,
                "password": password,
                "account_type": "RIDER",
                "remember_me": True,
            },
            format="json",
        )

    def test_rider_can_login_with_email_and_access_dashboard(self):
        response = self.login(self.rider.email, "rider-password-123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["account_type"], "RIDER")
        self.assertTrue(response.data["access"])
        self.assertTrue(response.data["refresh"])
        self.assertEqual(AccessToken(response.data["access"])["account_type"], "RIDER")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        dashboard = self.client.get("/api/v1/riders/dashboard/")

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["username"], self.rider.username)

    def test_rider_can_login_with_username(self):
        response = self.login(self.rider.username, "rider-password-123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["id"], str(self.rider.id))

    def test_non_rider_cannot_login_to_rider_mobile(self):
        response = self.login(self.customer.email, "customer-password-123")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "forbidden")
        self.assertEqual(response.data["message"], "This account is not allowed to use this login.")

    def test_invalid_password_returns_frontend_message(self):
        response = self.login(self.rider.email, "wrong-password")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_credentials")
        self.assertEqual(response.data["message"], "Invalid username/email or password.")

    def test_refresh_token_restores_dashboard_access(self):
        login = self.login(self.rider.email, "rider-password-123")
        refresh = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )

        self.assertEqual(refresh.status_code, 200)
        self.assertTrue(refresh.data["access"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.data['access']}")

        dashboard = self.client.get("/api/v1/riders/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["username"], self.rider.username)

    def test_multi_role_rider_session_can_refresh(self):
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        self.rider.roles.add(merchant_role)
        login = self.login(self.rider.email, "rider-password-123")

        refresh = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )

        self.assertEqual(login.status_code, 200)
        self.assertEqual(refresh.status_code, 200)

    def test_mobile_logout_revokes_refresh_without_request_body(self):
        login = self.login(self.rider.email, "rider-password-123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        logout = self.client.post("/api/v1/auth/logout/", {}, format="json")
        self.client.credentials()
        refresh = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )

        self.assertEqual(logout.status_code, 200)
        self.assertEqual(refresh.status_code, 401)
