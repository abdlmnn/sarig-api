from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User


class LogoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="logout_user",
            email="logout@test.com",
            password="pw12345",
        )

    def test_logout_blacklists_refresh_token(self):
        token_res = self.client.post(
            "/api/v1/auth/token/",
            {"username": "logout_user", "password": "pw12345"},
            format="json",
        )
        self.assertEqual(token_res.status_code, 200)
        refresh = token_res.data["refresh"]
        access = token_res.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        logout_res = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(logout_res.status_code, 200)

        refresh_res = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(refresh_res.status_code, 401)
