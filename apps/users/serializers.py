from rest_framework import serializers
from .models import Role, User, Profile, Address


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "phone_number", "roles")


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "phone_number",
            "password",
        )

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            phone_number=validated_data["phone_number"],
            password=validated_data["password"],
        )

        customer_role = Role.objects.get(name="customer")
        user.roles.add(customer_role)

        return user


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = (
            "id",
            "user",
            "avatar",
            "date_of_birth",
        )


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "user",
            "label",
            "latitude",
            "longitude",
            "street_address",
            "is_default",
        )
