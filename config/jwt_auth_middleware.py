from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def _get_user_from_token(token):
    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        return jwt_auth.get_user(validated_token)
    except (InvalidToken, TokenError):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Authenticates WebSocket clients with ?token=<access_token>.
    Session auth can still populate scope["user"] before this middleware runs.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        user = scope.get("user")
        if user and user.is_authenticated:
            return await self.app(scope, receive, send)

        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]
        scope["user"] = await _get_user_from_token(token) if token else AnonymousUser()
        return await self.app(scope, receive, send)
