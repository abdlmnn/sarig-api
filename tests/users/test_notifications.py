from unittest.mock import patch
from django.test import TestCase, override_settings
from apps.users.models import User, DeviceToken
from apps.users.notifications import PushNotificationService


class PushNotificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="notify_user", email="notify@test.com", password="pw12345"
        )

    def test_send_push_returns_false_when_no_tokens(self):
        sent = PushNotificationService.send_push(self.user, "Hello", "World")
        self.assertFalse(sent)

    @override_settings(ENABLE_FCM_PUSH=False)
    def test_send_push_returns_true_when_fcm_disabled_and_token_exists(self):
        DeviceToken.objects.create(user=self.user, token="tok1", device_type="ANDROID")
        sent = PushNotificationService.send_push(self.user, "Hello", "World")
        self.assertTrue(sent)

    @override_settings(ENABLE_FCM_PUSH=True, FCM_SERVER_KEY="abc123")
    @patch("apps.users.notifications.requests.post")
    def test_send_push_calls_fcm_when_enabled(self, mock_post):
        DeviceToken.objects.create(user=self.user, token="tok1", device_type="ANDROID")
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "ok"

        sent = PushNotificationService.send_push(
            self.user, "Order Update", "Accepted", {"order_id": "1"}
        )

        self.assertTrue(sent)
        mock_post.assert_called_once()
