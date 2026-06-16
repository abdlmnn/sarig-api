from rest_framework import serializers
from .models import BusinessType, DeliveryTime, MerchantApplication, RiderApplication


class MerchantApplicationSerializer(serializers.ModelSerializer):
    applicant = serializers.HiddenField(default=serializers.CurrentUserDefault())
    business_type = serializers.CharField()
    delivery_time = serializers.CharField()

    class Meta:
        model = MerchantApplication
        fields = [
            "id",
            "applicant",
            "business_name",
            "owner_first_name",
            "owner_last_name",
            "company_email",
            "contact_number",
            "business_type",
            "delivery_time",
            "branch_name",
            "business_address",
            "city",
            "barangay",
            "province",
            "postal_code",
            "street",
            "pinned_address",
            "latitude",
            "longitude",
            "dti_sec_certificate",
            "mayors_permit",
            "bir_cor",
            "halal_certification",
            "owner_valid_id",
            "storefront_photo",
            "status",
            "admin_remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "admin_remarks", "created_at", "updated_at"]

    def validate_business_type(self, value):
        normalized = str(value).strip().upper()
        if normalized not in BusinessType.values:
            raise serializers.ValidationError("Use SHOP or RESTAURANT.")
        return normalized

    def validate_delivery_time(self, value):
        normalized = str(value).strip().upper().replace(" ", "_")
        if normalized == "ALLDAY":
            normalized = DeliveryTime.ALL_DAY
        if normalized not in DeliveryTime.values:
            raise serializers.ValidationError("Use MORNING, AFTERNOON, EVENING, or ALL_DAY.")
        return normalized

    def validate(self, attrs):
        required_fields = [
            "business_name",
            "owner_first_name",
            "owner_last_name",
            "company_email",
            "contact_number",
            "business_type",
            "delivery_time",
            "business_address",
            "city",
            "barangay",
            "province",
            "postal_code",
            "street",
            "latitude",
            "longitude",
        ]
        missing_fields = [field for field in required_fields if attrs.get(field) in (None, "")]
        if missing_fields:
            raise serializers.ValidationError({field: "This field is required." for field in missing_fields})
        return attrs


class RiderApplicationSerializer(serializers.ModelSerializer):
    applicant = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = RiderApplication
        fields = [
            "id",
            "applicant",
            "vehicle_type",
            "plate_number",
            "professional_drivers_license",
            "lto_or_cr",
            "nbi_clearance",
            "barangay_clearance",
            "status",
            "admin_remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "admin_remarks", "created_at", "updated_at"]
