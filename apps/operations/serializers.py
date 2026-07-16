from rest_framework import serializers


class AdminMerchantActionSerializer(serializers.Serializer):
    ACTIONS = (
        "PAUSE_ACCOUNT",
        "REACTIVATE_ACCOUNT",
        "STOP_ORDERS",
        "RETURN_TO_SCHEDULE",
    )

    action = serializers.ChoiceField(choices=ACTIONS)
    reason = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate(self, attrs):
        if not attrs.get("reason"):
            raise serializers.ValidationError({"reason": "A reason is required for this action."})
        return attrs


class AdminRiderActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("SUSPEND_ACCOUNT", "REACTIVATE_ACCOUNT"))
    reason = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate_reason(self, value):
        if not value:
            raise serializers.ValidationError("A reason is required for this action.")
        return value
