from rest_framework import serializers
from .models import (
  User,
  UserProfile,
  Barangay,
)

class UserRegisterSerializer(serializers.ModelSerializer):
  password = serializers.CharField(
    write_only=True,
    required=True
  )

  class Meta:
    model = User
    fields = [
      'id',
      'username',
      'email',
      'password'
    ]

  def create(self, validated_data):
    password = validated_data.pop('password')
    user = User(**validated_data)
    user.set_password(password)
    user.save()
    return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class BarangaySerializer(serializers.ModelSerializer):
  class Meta:
    model = Barangay
    fields = [
      'id',
      'name'
    ]

class UserProfileSerializer(serializers.ModelSerializer):
  user = UserSerializer(
    read_only=True
  )
  barangay = serializers.PrimaryKeyRelatedField(
      queryset=Barangay.objects.all(),
      write_only=True,
      required=False
  )
  barangay_details = BarangaySerializer(
      source='barangay',
      read_only=True
  )

  class Meta:
    model = UserProfile
    fields = [
      'id',
      'user',
      'role',
      'phone_number',
      'barangay',
      'barangay_details',
      'verification_status',
      'created_at'
    ]
    read_only_fields = [
      'created_at',
      'verification_status'
    ]
