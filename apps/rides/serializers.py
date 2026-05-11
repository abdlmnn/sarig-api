from django.conf import settings
from rest_framework import serializers

from decimal import Decimal

from .models import Ride, RideEvent, RideStatus
from .realtime import publish_ride_event
from .services import RideAssignmentService, RideFareService


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
        try:
            publish_ride_event(ride, "RIDE_REQUESTED", {"status": ride.status})
        except Exception:
            pass
        if settings.JOYRIDE_ENABLE_AUTO_MATCHING:
            prior_status = ride.status
            ride = RideAssignmentService.auto_assign_best_rider(ride)
            if ride.status != prior_status and ride.rider_id:
                RideEvent.objects.create(
                    ride=ride,
                    event_type="RIDE_AUTO_ASSIGNED",
                    actor=None,
                    payload={"status": ride.status, "rider_id": str(ride.rider_id)},
                )
                try:
                    publish_ride_event(
                        ride,
                        "RIDE_AUTO_ASSIGNED",
                        {"status": ride.status, "rider_id": str(ride.rider_id)},
                    )
                except Exception:
                    pass
        return ride


class RideStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RideStatus.choices)


class RideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = "__all__"


class RideAssignSerializer(serializers.Serializer):
    rider_id = serializers.UUIDField()


class RideCancelSerializer(serializers.Serializer):
    cancel_reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
