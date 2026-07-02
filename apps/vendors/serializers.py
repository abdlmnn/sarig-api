from rest_framework import serializers
from apps.common.validators import validate_image_upload
from .models import BusinessVertical, Store, StoreManualOverride


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
            "branch_name",
            "company_email",
            "contact_number",
            "delivery_time",
            "latitude",
            "longitude",
            "street_address",
            "city",
            "barangay",
            "province",
            "postal_code",
            "pinned_address",
            "commission_rate",
            "is_open",
            "is_active",
            "image",
            "rating",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "owner",
            "commission_rate",
            "is_active",
            "rating",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["owner"] = request.user
        return super().create(validated_data)

    def validate_image(self, value):
        validate_image_upload(value)
        return value


class StoreStatusUpdateSerializer(serializers.Serializer):
    manual_override = serializers.ChoiceField(
        choices=StoreManualOverride.choices,
        allow_null=True,
        required=False,
    )
    reason = serializers.CharField(allow_blank=True, max_length=255, required=False)
