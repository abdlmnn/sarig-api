from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from apps.users.models import Role, User


class RoleCookieSessionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.admin = User.objects.create_superuser(
            username="cookie-admin",
            email="cookie-admin@example.com",
            password="password123",
        )
        self.merchant = User.objects.create_user(
            username="cookie-merchant",
            email="cookie-merchant@example.com",
            password="password123",
        )
        merchant_role, _ = Role.objects.get_or_create(name="Merchant")
        self.merchant.roles.add(merchant_role)
        self.csrf_token = self.client.get("/api/v1/auth/csrf/").data["csrf_token"]

    def tearDown(self):
        cache.clear()

    def post(self, path, data=None):
        return self.client.post(
            path,
            data or {},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )

    def login_admin(self, remember_me=True):
        return self.post(
            "/api/v1/auth/admin/login/",
            {
                "identifier": self.admin.email,
                "password": "password123",
                "remember_me": remember_me,
            },
        )

    def login_merchant(self, remember_me=True):
        return self.post(
            "/api/v1/auth/merchant/login/",
            {
                "identifier": self.merchant.email,
                "password": "password123",
                "remember_me": remember_me,
            },
        )

    def test_login_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            "/api/v1/auth/admin/login/",
            {"identifier": self.admin.email, "password": "password123"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_login_sets_configured_httponly_cookie_without_refresh_body(self):
        response = self.login_admin()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("refresh", response.data)
        self.assertEqual(response.data["account_type"], "ADMIN")
        self.assertEqual(response["Cache-Control"], "no-store")
        cookie = response.cookies[settings.AUTH_REFRESH_COOKIE_NAMES["ADMIN"]]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(bool(cookie["secure"]), settings.AUTH_COOKIE_SECURE)
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/")
        self.assertGreater(int(cookie["max-age"]), 0)

    def test_cookie_prefix_matches_configured_transport_security(self):
        for cookie_name in settings.AUTH_REFRESH_COOKIE_NAMES.values():
            self.assertEqual(
                cookie_name.startswith("__Host-"),
                settings.AUTH_COOKIE_SECURE,
            )

    def test_non_remembered_cookie_has_no_persistent_expiry(self):
        response = self.login_merchant(remember_me=False)
        cookie = response.cookies[settings.AUTH_REFRESH_COOKIE_NAMES["MERCHANT"]]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(cookie["max-age"], "")
        self.assertEqual(cookie["expires"], "")

    def test_admin_and_merchant_cookies_coexist(self):
        self.assertEqual(self.login_admin().status_code, 200)
        self.assertEqual(self.login_merchant().status_code, 200)

        self.assertIn(settings.AUTH_REFRESH_COOKIE_NAMES["ADMIN"], self.client.cookies)
        self.assertIn(settings.AUTH_REFRESH_COOKIE_NAMES["MERCHANT"], self.client.cookies)

    def test_role_refresh_rotates_only_matching_cookie(self):
        self.login_admin()
        self.login_merchant()
        merchant_cookie_before = self.client.cookies[
            settings.AUTH_REFRESH_COOKIE_NAMES["MERCHANT"]
        ].value

        response = self.post("/api/v1/auth/admin/refresh/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("refresh", response.data)
        self.assertEqual(response.data["account_type"], "ADMIN")
        self.assertEqual(
            self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAMES["MERCHANT"]].value,
            merchant_cookie_before,
        )

    def test_rotated_refresh_token_cannot_be_reused(self):
        login = self.login_admin()
        cookie_name = settings.AUTH_REFRESH_COOKIE_NAMES["ADMIN"]
        previous_token = login.cookies[cookie_name].value
        self.assertEqual(self.post("/api/v1/auth/admin/refresh/").status_code, 200)
        self.client.cookies[cookie_name] = previous_token

        response = self.post("/api/v1/auth/admin/refresh/")

        self.assertEqual(response.status_code, 401)

    def test_refresh_requires_csrf(self):
        login = self.login_admin()
        client = APIClient(enforce_csrf_checks=True)
        cookie_name = settings.AUTH_REFRESH_COOKIE_NAMES["ADMIN"]
        client.cookies[cookie_name] = login.cookies[cookie_name].value

        response = client.post("/api/v1/auth/admin/refresh/", {}, format="json")

        self.assertEqual(response.status_code, 403)

    def test_wrong_role_token_is_rejected(self):
        admin_response = self.login_admin()
        admin_cookie = admin_response.cookies[
            settings.AUTH_REFRESH_COOKIE_NAMES["ADMIN"]
        ].value
        self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAMES["MERCHANT"]] = admin_cookie

        response = self.post("/api/v1/auth/merchant/refresh/")

        self.assertEqual(response.status_code, 401)

    def test_admin_logout_keeps_merchant_cookie(self):
        self.login_admin()
        self.login_merchant()
        merchant_cookie_before = self.client.cookies[
            settings.AUTH_REFRESH_COOKIE_NAMES["MERCHANT"]
        ].value

        response = self.post("/api/v1/auth/admin/logout/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.cookies[settings.AUTH_REFRESH_COOKIE_NAMES["MERCHANT"]].value,
            merchant_cookie_before,
        )

    def test_inactive_account_cannot_refresh(self):
        self.login_merchant()
        self.merchant.is_active = False
        self.merchant.save(update_fields=["is_active"])

        self.assertTrue(
            BlacklistedToken.objects.filter(token__user=self.merchant).exists()
        )

        response = self.post("/api/v1/auth/merchant/refresh/")

        self.assertEqual(response.status_code, 401)
