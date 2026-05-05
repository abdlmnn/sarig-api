from rest_framework import serializers
from .models import MerchantApplication, RiderApplication


class MerchantApplicationSerializer(serializers.ModelSerializer):
    applicant = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = MerchantApplication
        fields = [
            "id",
            "applicant",
            "business_name",
            "business_address",
            "contact_number",
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
