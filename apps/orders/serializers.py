from rest_framework import serializers
from .models import DeliveryMethod, Order, OrderItem
from .services import order_tracking_payload
from apps.payments.models import PaymentMethod


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
    address_text = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
    )
    promo_code = serializers.CharField(required=False, allow_blank=True, max_length=64)

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
