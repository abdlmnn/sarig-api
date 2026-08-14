from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework import serializers
from rest_framework.reverse import reverse
from apps.common.validators import validate_document_upload

from .models import DeliveryMethod, DeliveryOption, Order, OrderItem
from .services import order_tracking_payload
from apps.payments.models import PaymentMethod


class CoordinateField(serializers.Field):
    default_error_messages = {"invalid": "Enter a valid coordinate."}

    def to_internal_value(self, data):
        try:
            value = Decimal(str(data))
            if not value.is_finite():
                self.fail("invalid")
            return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            self.fail("invalid")

    def to_representation(self, value):
        return str(value)


class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)
    modifier_item_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        max_length=30,
    )
    special_instructions = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )


class CheckoutRequestSerializer(serializers.Serializer):
    store_id = serializers.UUIDField()
    items = CheckoutItemSerializer(many=True, allow_empty=False)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    delivery_method = serializers.ChoiceField(
        choices=DeliveryMethod.choices, default=DeliveryMethod.DELIVERY
    )
    delivery_option = serializers.ChoiceField(
        choices=DeliveryOption.choices, default=DeliveryOption.STANDARD
    )
    address_text = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    latitude = CoordinateField(required=False)
    longitude = CoordinateField(required=False)
    promo_code = serializers.CharField(required=False, allow_blank=True, max_length=64)
    prescription_files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True,
        max_length=5,
    )

    def validate_prescription_files(self, value):
        for uploaded_file in value:
            validate_document_upload(uploaded_file)
        return value

    def validate_latitude(self, value):
        if not (-90 <= value <= 90):
            raise serializers.ValidationError("Latitude out of valid range.")
        return value

    def validate_longitude(self, value):
        if not (-180 <= value <= 180):
            raise serializers.ValidationError("Longitude out of valid range.")
        return value

    def validate(self, attrs):
        if attrs["delivery_method"] == DeliveryMethod.DELIVERY:
            if not attrs.get("address_text"):
                raise serializers.ValidationError(
                    {"address_text": "Address is required for delivery."}
                )
            if "latitude" not in attrs or "longitude" not in attrs:
                raise serializers.ValidationError(
                    {"location": "A delivery location is required."}
                )
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source="product.name")
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "total_price",
            "special_instructions",
        ]
        read_only_fields = ["id"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source="customer.get_full_name")
    store_name = serializers.ReadOnlyField(source="store.name")
    store_vertical_slug = serializers.ReadOnlyField(source="store.vertical.slug")
    tracking = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    prescriptions = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "customer_name",
            "store",
            "store_name",
            "store_vertical_slug",
            "rider",
            "status",
            "delivery_method",
            "delivery_address_text",
            "delivery_latitude",
            "delivery_longitude",
            "subtotal",
            "delivery_fee",
            "system_fee",
            "total_amount",
            "items",
            "created_at",
            "updated_at",
            "delivered_at",
            "estimated_arrival_time",
            "cancel_reason",
            "tracking",
            "payment",
            "prescriptions",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_at",
            "updated_at",
            "delivered_at",
            "estimated_arrival_time",
            "cancel_reason",
            "tracking",
            "payment",
            "prescriptions",
        ]

    def get_tracking(self, order):
        return order_tracking_payload(order)

    def get_payment(self, order):
        payment = order.payment_attempts.first()
        if not payment:
            return None
        return {
            "id": str(payment.id),
            "method": payment.payment_method,
            "method_label": payment.get_payment_method_display(),
            "status": payment.status,
            "status_label": payment.get_status_display(),
            "amount": str(payment.amount),
            "reference": payment.external_transaction_id or "",
            "updated_at": payment.updated_at.isoformat(),
        }

    def get_prescriptions(self, order):
        request = self.context.get("request")
        return [
            {
                "id": str(prescription.id),
                "file_name": prescription.file.name.rsplit("/", 1)[-1],
                "file_url": (
                    reverse(
                        "v1:prescription-file",
                        args=[prescription.id],
                        request=request,
                    )
                    if prescription.file
                    else ""
                ),
                "status": prescription.status,
                "status_label": prescription.get_status_display(),
                "pharmacy_note": prescription.pharmacy_note,
            }
            for prescription in order.prescriptions.all()
        ]
