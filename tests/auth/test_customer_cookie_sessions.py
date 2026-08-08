from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import Role, User


class CustomerCookieSessionTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.customer = User.objects.create_user(
            username="customer-cookie",
            email="customer-cookie@example.com",
            password="password123",
        )
        customer_role, _ = Role.objects.get_or_create(name="Customer")
        self.customer.roles.add(customer_role)
        self.csrf_token = self.client.get("/api/v1/auth/csrf/").data["csrf_token"]

    def post(self, path, data=None):
        return self.client.post(
            path,
            data or {},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    def test_customer_cookie_session_login_refresh_and_logout(self):
        login = self.post(
            "/api/v1/auth/customer/login/",
            {
                "identifier": self.customer.email,
                "password": "password123",
                "remember_me": True,
            },
        )

        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.data["account_type"], "CUSTOMER")
        self.assertNotIn("refresh", login.data)
        cookie_name = settings.AUTH_REFRESH_COOKIE_NAMES["CUSTOMER"]
        self.assertTrue(login.cookies[cookie_name]["httponly"])

        refresh = self.post("/api/v1/auth/customer/refresh/")
        self.assertEqual(refresh.status_code, 200)
        self.assertEqual(refresh.data["account_type"], "CUSTOMER")

        logout = self.post("/api/v1/auth/customer/logout/")
        self.assertEqual(logout.status_code, 200)

    def test_merchant_cannot_use_customer_scope(self):
        merchant = User.objects.create_user(
            username="merchant-customer-scope",
            email="merchant-customer-scope@example.com",
            password="password123",
        )
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        merchant.roles.add(merchant_role)

        response = self.post(
            "/api/v1/auth/customer/login/",
            {
                "identifier": merchant.email,
                "password": "password123",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "forbidden")

    def test_customer_can_create_address_without_submitting_user_id(self):
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            "/api/v1/users/me/addresses/",
            {
                "label": "Home",
                "latitude": "8.003400",
                "longitude": "124.283900",
                "street_address": "Marawi City",
                "is_default": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"], self.customer.id)
