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
    manual_override = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    status = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    reason = serializers.CharField(
        allow_blank=True,
        max_length=255,
        required=False,
    )

    STATUS_TO_OVERRIDE = {
        "OPEN": StoreManualOverride.OPEN_NOW,
        "OPEN_NOW": StoreManualOverride.OPEN_NOW,
        "CLOSED": StoreManualOverride.CLOSED_TEMPORARILY,
        "CLOSED_TEMPORARILY": StoreManualOverride.CLOSED_TEMPORARILY,
        "PAUSED": StoreManualOverride.PAUSED_ORDERS,
        "PAUSED_ORDERS": StoreManualOverride.PAUSED_ORDERS,
        "NORMAL": None,
        "AUTO": None,
        "SCHEDULED": None,
        "NONE": None,
        "": None,
    }

    def validate(self, attrs):
        raw_value = attrs.get("manual_override", attrs.get("status"))
        if raw_value is None:
            attrs["manual_override"] = None
            return attrs

        normalized = str(raw_value).strip().upper().replace("-", "_").replace(" ", "_")
        if normalized not in self.STATUS_TO_OVERRIDE:
            allowed = ", ".join(sorted(value for value in self.STATUS_TO_OVERRIDE if value))
            raise serializers.ValidationError(
                {
                    "status": (
                        "Unsupported store status. "
                        f"Use one of: {allowed}."
                    )
                }
            )

        attrs["manual_override"] = self.STATUS_TO_OVERRIDE[normalized]
        return attrs
