from rest_framework import serializers
from .models import BusinessVertical, Store


class BusinessVerticalSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessVertical
        fields = "__all__"


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = [
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
            "image",
            "rating",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("owner", "rating", "created_at", "updated_at")

    def create(self, validated_data):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["owner"] = request.user
        return super().create(validated_data)
