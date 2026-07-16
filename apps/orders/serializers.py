from rest_framework import serializers
from .models import DeliveryMethod, Order, OrderItem
from apps.payments.models import PaymentMethod


class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)
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
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
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
        if attrs["delivery_method"] == DeliveryMethod.DELIVERY and not attrs.get("address_text"):
            raise serializers.ValidationError({"address_text": "Address is required for delivery."})
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

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "customer_name",
            "store",
            "store_name",
            "rider",
            "status",
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
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at", "delivered_at"]


class MerchantOrderDetailSerializer(OrderSerializer):
    tracking = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + [
            "delivery_method",
            "estimated_arrival_time",
            "tracking",
        ]

    def get_tracking(self, order):
        rider_profile = getattr(order.rider, "rider_profile", None) if order.rider else None
        rider = None
        if (
            rider_profile
            and rider_profile.current_latitude is not None
            and rider_profile.current_longitude is not None
        ):
            rider = {
                "latitude": str(rider_profile.current_latitude),
                "longitude": str(rider_profile.current_longitude),
                "last_updated_at": rider_profile.last_location_update.isoformat(),
            }

        return {
            "store": {
                "latitude": str(order.store.latitude),
                "longitude": str(order.store.longitude),
            },
            "customer": {
                "latitude": str(order.delivery_latitude),
                "longitude": str(order.delivery_longitude),
            },
            "rider": rider,
        }
