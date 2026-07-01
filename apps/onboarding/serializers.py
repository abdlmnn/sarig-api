from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.common.validators import validate_document_upload, validate_image_upload
from apps.locations.services import is_inside_marawi
from apps.vendors.models import BusinessVertical

from .models import (
    ApplicationEditToken,
    ApplicationStatus,
    BusinessType,
    DeliveryTime,
    LocationSource,
    MerchantApplication,
    RiderApplication,
    VehicleType,
)


def normalize_choice(value, allowed_values, aliases=None):
    aliases = aliases or {}
    normalized = str(value).strip().upper().replace(" ", "_")
    normalized = aliases.get(normalized, normalized)
    if normalized not in allowed_values:
        raise serializers.ValidationError(f"Use one of: {', '.join(allowed_values)}.")
    return normalized


class MerchantApplicationSerializer(serializers.ModelSerializer):
    business_type = serializers.CharField()
    delivery_time = serializers.CharField()
    street = serializers.CharField(required=False, allow_blank=True, default="")
    business_vertical_slug = serializers.SlugRelatedField(
        source="business_vertical",
        slug_field="slug",
        queryset=BusinessVertical.objects.filter(is_active=True),
        required=False,
        write_only=True,
    )

    class Meta:
        model = MerchantApplication
        fields = [
            "application_id",
            "business_name",
            "owner_first_name",
            "owner_last_name",
            "company_email",
            "contact_number",
            "business_type",
            "business_vertical",
            "business_vertical_slug",
            "delivery_time",
            "branch_name",
            "terms_accepted",
            "business_address",
            "street",
            "barangay",
            "city",
            "province",
            "postal_code",
            "location_source",
            "pinned_address",
            "latitude",
            "longitude",
            "dti_sec_certificate",
            "mayors_permit",
            "bir_cor",
            "owner_valid_id",
            "storefront_photo",
            "pharmacy_license",
            "status",
            "admin_remarks",
            "requested_fields",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["application_id", "business_vertical", "status", "admin_remarks", "requested_fields", "created_at", "updated_at"]

    def validate_business_type(self, value):
        return normalize_choice(value, BusinessType.values, {"SHOP": BusinessType.SHOP, "RESTAURANT": BusinessType.RESTAURANT})

    def validate_delivery_time(self, value):
        return normalize_choice(value, DeliveryTime.values, {"ALLDAY": DeliveryTime.ALL_DAY})

    def validate_dti_sec_certificate(self, value):
        validate_document_upload(value)
        return value

    def validate_mayors_permit(self, value):
        validate_document_upload(value)
        return value

    def validate_bir_cor(self, value):
        validate_document_upload(value)
        return value

    def validate_owner_valid_id(self, value):
        validate_document_upload(value)
        return value

    def validate_storefront_photo(self, value):
        validate_image_upload(value)
        return value

    def validate_pharmacy_license(self, value):
        validate_document_upload(value)
        return value

    def validate(self, attrs):
        if not attrs.get("terms_accepted"):
            raise serializers.ValidationError({"terms_accepted": "Terms must be accepted."})
        if not attrs.get("business_vertical"):
            business_type = attrs.get("business_type", BusinessType.RESTAURANT)
            vertical_slug = "restaurant" if business_type == BusinessType.RESTAURANT else "general-store"
            vertical = BusinessVertical.objects.filter(slug=vertical_slug, is_active=True).first()
            if vertical:
                attrs["business_vertical"] = vertical
        business_vertical = attrs.get("business_vertical")
        required_documents = business_vertical.required_documents if business_vertical else []
        missing_documents = [
            field
            for field in required_documents
            if field in {"pharmacy_license"}
            and attrs.get(field, getattr(self.instance, field, None)) in (None, "")
        ]
        if missing_documents:
            raise serializers.ValidationError(
                {field: "This document is required for the selected business category." for field in missing_documents}
            )
        if attrs.get("location_source") == LocationSource.PIN:
            missing = [field for field in ("pinned_address", "latitude", "longitude") if attrs.get(field) in (None, "")]
            if missing:
                raise serializers.ValidationError({field: "This field is required when location_source is pin." for field in missing})
            if not is_inside_marawi(attrs["latitude"], attrs["longitude"]):
                raise serializers.ValidationError(
                    {"coordinates": "Location is outside the Marawi City service boundary."}
                )
        return attrs


class RiderApplicationSerializer(serializers.ModelSerializer):
    vehicle_type = serializers.CharField()

    class Meta:
        model = RiderApplication
        fields = [
            "application_id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "terms_accepted",
            "current_address",
            "barangay",
            "city",
            "province",
            "postal_code",
            "emergency_contact_name",
            "emergency_contact_number",
            "emergency_contact_relationship",
            "vehicle_type",
            "vehicle_brand",
            "plate_number",
            "vehicle_photo_front",
            "vehicle_photo_back",
            "professional_drivers_license",
            "lto_or_cr",
            "nbi_clearance",
            "barangay_clearance",
            "status",
            "admin_remarks",
            "requested_fields",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["application_id", "status", "admin_remarks", "requested_fields", "created_at", "updated_at"]

    def validate_vehicle_type(self, value):
        return normalize_choice(value, VehicleType.values)

    def validate_vehicle_photo_front(self, value):
        validate_image_upload(value)
        return value

    def validate_vehicle_photo_back(self, value):
        validate_image_upload(value)
        return value

    def validate_professional_drivers_license(self, value):
        validate_document_upload(value)
        return value

    def validate_lto_or_cr(self, value):
        validate_document_upload(value)
        return value

    def validate_nbi_clearance(self, value):
        validate_document_upload(value)
        return value

    def validate_barangay_clearance(self, value):
        validate_document_upload(value)
        return value

    def validate(self, attrs):
        if not attrs.get("terms_accepted"):
            raise serializers.ValidationError({"terms_accepted": "Terms must be accepted."})
        if attrs.get("vehicle_type") in (VehicleType.MOTORCYCLE, VehicleType.CAR) and not attrs.get("plate_number"):
            raise serializers.ValidationError({"plate_number": "Plate number is required for motorcycle and car applications."})
        return attrs


class ApplicationIdSerializer(serializers.Serializer):
    application_id = serializers.CharField()


class StatusResponseSerializer(serializers.Serializer):
    application_id = serializers.CharField()
    type = serializers.CharField()
    status = serializers.CharField()
    submitted_at = serializers.DateTimeField(source="created_at")
    updated_at = serializers.DateTimeField()
    applicant_name = serializers.CharField()
    business_name = serializers.CharField(required=False)
    admin_remarks = serializers.CharField()
    next_action = serializers.CharField()
    can_edit = serializers.BooleanField()
    edit_url = serializers.CharField(allow_null=True)


class RequestChangesSerializer(serializers.Serializer):
    admin_remarks = serializers.CharField()
    requested_fields = serializers.ListField(child=serializers.CharField(), allow_empty=False)


class RejectApplicationSerializer(serializers.Serializer):
    admin_remarks = serializers.CharField()


class AccountSetupSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if get_user_model().objects.filter(username=value).exists():
            raise serializers.ValidationError("Username is already taken.")
        return value


class EditTokenSerializer(serializers.Serializer):
    application_id = serializers.CharField()
    type = serializers.CharField()
    status = serializers.CharField()
    requested_fields = serializers.ListField(child=serializers.CharField())
    admin_remarks = serializers.CharField()
    application = serializers.DictField()


class ApplicationEditSerializer(serializers.Serializer):
    def validate(self, attrs):
        token = self.context.get("edit_token")
        if not isinstance(token, ApplicationEditToken):
            raise serializers.ValidationError("Invalid edit token.")
        allowed = set(token.requested_fields or [])
        submitted = set(self.initial_data.keys())
        disallowed = submitted - allowed
        if disallowed:
            raise serializers.ValidationError({field: "This field was not requested for editing." for field in sorted(disallowed)})
        return attrs
