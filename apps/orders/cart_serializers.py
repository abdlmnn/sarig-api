from decimal import Decimal

from rest_framework import serializers
from django.utils import timezone

from apps.vendors.utils import PH_TZ, store_availability_payload

from .models import CustomerCart, CustomerCartItem


class CartItemMutationSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=99)
    special_instructions = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )


class CartSyncItemSerializer(CartItemMutationSerializer):
    product_id = serializers.UUIDField()
    line_key = serializers.CharField(required=False, allow_blank=True, max_length=1500)
    modifier_item_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        max_length=30,
    )


class CartSyncBasketSerializer(serializers.Serializer):
    store_id = serializers.UUIDField()
    items = CartSyncItemSerializer(many=True, allow_empty=False)


class CartSyncSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(
        choices=("MERGE", "REPLACE"),
        default="MERGE",
    )
    baskets = CartSyncBasketSerializer(many=True, allow_empty=True)

    def validate_baskets(self, baskets):
        store_ids = [basket["store_id"] for basket in baskets]
        if len(store_ids) != len(set(store_ids)):
            raise serializers.ValidationError("Each store may appear only once.")
        return baskets


class CustomerCartItemSerializer(serializers.ModelSerializer):
    line_key = serializers.CharField(read_only=True)
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    name = serializers.CharField(source="product.name", read_only=True)
    base_price = serializers.DecimalField(
        source="product.price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()
    requires_prescription = serializers.BooleanField(
        source="product.requires_prescription",
        read_only=True,
    )
    modifiers = serializers.SerializerMethodField()

    class Meta:
        model = CustomerCartItem
        fields = (
            "product_id",
            "line_key",
            "name",
            "base_price",
            "price",
            "image",
            "quantity",
            "special_instructions",
            "available",
            "requires_prescription",
            "modifiers",
        )

    def get_image(self, item):
        if not item.product.image:
            return ""
        request = self.context.get("request")
        url = item.product.image.url
        return request.build_absolute_uri(url) if request else url

    def get_available(self, item):
        modifiers_available = all(
            modifier.is_available for modifier in item.modifiers.all()
        )
        return bool(item.product.in_stock and modifiers_available)

    def get_price(self, item):
        modifier_total = sum(
            (modifier.extra_price for modifier in item.modifiers.all()),
            Decimal("0.00"),
        )
        return str(item.product.price + modifier_total)

    def get_modifiers(self, item):
        return [
            {
                "id": str(modifier.id),
                "group_id": str(modifier.group_id),
                "group_name": modifier.group.name,
                "name": modifier.name,
                "extra_price": str(modifier.extra_price),
            }
            for modifier in item.modifiers.all()
        ]


class CustomerCartSerializer(serializers.ModelSerializer):
    store = serializers.SerializerMethodField()
    items = CustomerCartItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CustomerCart
        fields = ("id", "store", "items", "subtotal", "updated_at")

    def get_store(self, cart):
        store = cart.store
        availability = store_availability_payload(
            store,
            timezone.now().astimezone(PH_TZ),
        )
        return {
            "id": str(store.id),
            "name": store.name,
            "is_open": bool(store.is_active and availability["status"] == "OPEN"),
            "availability_status": availability["status"],
            "availability_label": availability["status_label"],
            "availability_reason": availability["status_reason"],
            "barangay": store.barangay,
            "city": store.city,
            "vertical": {
                "name": store.vertical.name,
                "slug": store.vertical.slug,
            },
            "rating": float(store.rating or 0),
        }

    def get_subtotal(self, cart):
        total = sum(
            (
                (
                    item.product.price
                    + sum(
                        (
                            modifier.extra_price
                            for modifier in item.modifiers.all()
                        ),
                        Decimal("0.00"),
                    )
                )
                * item.quantity
                for item in cart.items.all()
            ),
            Decimal("0.00"),
        )
        return str(total)
