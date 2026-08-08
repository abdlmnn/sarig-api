from datetime import timedelta

from django.conf import settings
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from .models import User


ACCOUNT_SCOPES = ("ADMIN", "MERCHANT", "CUSTOMER")


def cookie_name(account_type):
    return settings.AUTH_REFRESH_COOKIE_NAMES[account_type]


def refresh_lifetime(account_type, remember_me):
    if not remember_me:
        return timedelta(hours=settings.AUTH_SESSION_REFRESH_HOURS)
    if account_type == "ADMIN":
        return timedelta(days=settings.AUTH_ADMIN_REMEMBER_DAYS)
    if account_type == "CUSTOMER":
        return timedelta(days=settings.AUTH_CUSTOMER_REMEMBER_DAYS)
    return timedelta(days=settings.AUTH_MERCHANT_REMEMBER_DAYS)


def issue_refresh_token(user, account_type, remember_me):
    token = RefreshToken.for_user(user)
    token["account_type"] = account_type
    token["remember_me"] = bool(remember_me)
    token.set_exp(lifetime=refresh_lifetime(account_type, remember_me))
    return token


def set_refresh_cookie(response, token, account_type, remember_me):
    lifetime = refresh_lifetime(account_type, remember_me)
    response.set_cookie(
        key=cookie_name(account_type),
        value=str(token),
        max_age=int(lifetime.total_seconds()) if remember_me else None,
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path="/",
    )


def clear_refresh_cookie(response, account_type):
    response.delete_cookie(
        cookie_name(account_type),
        path="/",
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


def user_has_scope(user, account_type):
    if not user or not user.is_active:
        return False
    if account_type == "ADMIN":
        return bool(user.is_superuser and user.is_staff)
    if account_type == "MERCHANT":
        return bool(user.is_merchant and not user.is_superuser)
    if account_type == "CUSTOMER":
        return bool(user.is_customer and not user.is_superuser)
    return False


def validate_refresh_token(raw_token, account_type):
    token = RefreshToken(raw_token)
    if token.get("account_type") != account_type:
        raise TokenError("Refresh token scope does not match this endpoint.")

    user = User.objects.filter(id=token.get("user_id")).first()
    if not user_has_scope(user, account_type):
        raise TokenError("This account is no longer allowed to use this session.")
    return token, user


def rotate_refresh_token(raw_token, account_type):
    token, user = validate_refresh_token(raw_token, account_type)
    remember_me = bool(token.get("remember_me", False))
    serializer = TokenRefreshSerializer(data={"refresh": raw_token})
    serializer.is_valid(raise_exception=True)
    rotated = serializer.validated_data.get("refresh")
    next_token = RefreshToken(rotated) if rotated else token
    return serializer.validated_data["access"], next_token, user, remember_me


def revoke_user_refresh_tokens(user):
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
