from rest_framework import serializers
from .models import Order, OrderItem


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
