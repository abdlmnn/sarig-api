from datetime import timedelta

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.validators import validate_image_upload

from .models import Role, User, Profile, Address


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    is_customer = serializers.BooleanField(read_only=True)
    is_merchant = serializers.BooleanField(read_only=True)
    is_rider = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "is_customer",
            "is_merchant",
            "is_rider",
        )


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "phone_number",
            "password",
            "first_name",
            "last_name",
        )

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)

        # Default role is Customer
        customer_role, _ = Role.objects.get_or_create(name="Customer")
        user.roles.add(customer_role)

        return user


class RoleAwareLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(required=False, default=False)

    required_scope = None

    default_error_messages = {
        "invalid_credentials": "Invalid username/email or password.",
        "inactive": "This account is inactive.",
        "forbidden": "This account is not allowed to use this login.",
    }

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]
        user = self.get_user_by_identifier(identifier)
        if not user:
            raise self.auth_error("invalid_credentials")

        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=user.username,
            password=password,
        )
        if not authenticated_user:
            raise self.auth_error("invalid_credentials")
        if not authenticated_user.is_active:
            raise self.auth_error("inactive")
        if not self.is_allowed(authenticated_user):
            raise self.auth_error("forbidden")

        refresh = RefreshToken.for_user(authenticated_user)
        if attrs.get("remember_me"):
            refresh.set_exp(lifetime=timedelta(days=14))
        else:
            refresh.set_exp(lifetime=timedelta(hours=12))

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(authenticated_user).data,
            "account_type": self.required_scope,
            "remember_me": attrs.get("remember_me", False),
        }

    def get_user_by_identifier(self, identifier):
        if "@" in identifier:
            return User.objects.filter(email__iexact=identifier).first()
        return User.objects.filter(username__iexact=identifier).first()

    def is_allowed(self, user):
        if self.required_scope == "ADMIN":
            return bool(user.is_superuser)
        if self.required_scope == "MERCHANT":
            return bool(user.is_merchant and not user.is_superuser)
        return True

    def auth_error(self, code):
        return serializers.ValidationError(
            {
                "code": code,
                "message": self.error_messages[code],
            }
        )


class AdminLoginSerializer(RoleAwareLoginSerializer):
    required_scope = "ADMIN"


class MerchantLoginSerializer(RoleAwareLoginSerializer):
    required_scope = "MERCHANT"


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = "__all__"

    def validate_avatar(self, value):
        validate_image_upload(value)
        return value


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"
        read_only_fields = ("user",)

    def create(self, validated_data):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["user"] = request.user
        return super().create(validated_data)
