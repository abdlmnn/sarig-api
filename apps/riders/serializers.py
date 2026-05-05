from rest_framework import serializers
from .models import RiderProfile, RiderTransaction

class RiderTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderTransaction
        fields = ["id", "order", "amount", "transaction_type", "description", "created_at"]

class RiderProfileSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")
    transactions = RiderTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = RiderProfile
        fields = ["username", "is_online", "is_available", "balance", "vehicle_type", "transactions"]
