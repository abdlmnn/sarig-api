from rest_framework import serializers
from .models import BusinessVertical, Store

# GDAL IMPORT (COMMENTED FOR NOW)
# from django.contrib.gis.geos import Point


class BusinessVerticalSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessVertical
        fields = (
            "id",
            "name",
            "slug",
            "is_active",
        )


class StoreSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True)
    longitude = serializers.FloatField(write_only=True)

    class Meta:
        model = Store
        fields = (
            "id",
            "owner",
            "vertical",
            "name",
            "latitude",
            "longitude",
            "street_address",
            "city",
            "commission_rate",
            "is_open",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("owner", "created_at", "updated_at")

    def create(self, validated_data):
        lat = validated_data.pop("latitude")
        lng = validated_data.pop("longitude")

        # FUTURE GDAL (COMMENTED)
        # validated_data["location"] = Point(lng, lat)

        # CURRENT (ACTIVE)
        validated_data["latitude"] = lat
        validated_data["longitude"] = lng

        request = self.context.get("request")
        validated_data["owner"] = request.user

        return Store.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if "latitude" in validated_data and "longitude" in validated_data:
            lat = validated_data.pop("latitude")
            lng = validated_data.pop("longitude")
            instance.location = Point(lng, lat)

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # already stored fields
        data["latitude"] = instance.latitude
        data["longitude"] = instance.longitude

        return data
