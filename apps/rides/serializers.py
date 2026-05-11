from rest_framework import serializers

from decimal import Decimal

from .models import Ride, RideEvent, RideStatus
from .services import RideFareService


class RideCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = [
            "id",
            "requested_vehicle_type",
            "pickup_lat",
            "pickup_lng",
            "dropoff_lat",
            "dropoff_lng",
            "estimated_fare",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        validated_data["passenger"] = self.context["request"].user
        validated_data.setdefault("distance_km", Decimal("3.00"))
        validated_data.setdefault("duration_min", Decimal("10.00"))
        ride = super().create(validated_data)
        RideFareService.upsert_breakdown(
            ride=ride,
            vehicle_type=ride.requested_vehicle_type,
            distance_km=ride.distance_km,
            duration_min=ride.duration_min,
        )
        RideEvent.objects.create(
            ride=ride,
            event_type="RIDE_REQUESTED",
            actor=ride.passenger,
            payload={"status": ride.status},
        )
        return ride


class RideStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RideStatus.choices)


class RideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = "__all__"


class RideAssignSerializer(serializers.Serializer):
    rider_id = serializers.UUIDField()
