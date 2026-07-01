from rest_framework import serializers

from .services import is_inside_marawi


class CoordinateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)

    def validate_latitude(self, value):
        if not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude out of valid range.")
        return value

    def validate_longitude(self, value):
        if not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude out of valid range.")
        return value


class ReverseGeocodeSerializer(CoordinateSerializer):
    def validate(self, attrs):
        if not is_inside_marawi(attrs["latitude"], attrs["longitude"]):
            raise serializers.ValidationError(
                {"coordinates": "Location is outside the Marawi City service boundary."}
            )
        return attrs


class RouteEstimateSerializer(serializers.Serializer):
    origin = CoordinateSerializer()
    destination = CoordinateSerializer()


class DeliveryFeeEstimateSerializer(serializers.Serializer):
    store = CoordinateSerializer()
    customer = CoordinateSerializer()


class LocationSearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=255)
    limit = serializers.IntegerField(min_value=1, max_value=10, required=False, default=5)
