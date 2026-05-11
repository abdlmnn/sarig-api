from rest_framework import serializers

from .models import Ride, RideEvent, RideStatus


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
        ride = super().create(validated_data)
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

