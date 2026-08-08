from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product

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
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    name = serializers.CharField(source="product.name", read_only=True)
    price = serializers.DecimalField(
        source="product.price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    image = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()
    requires_prescription = serializers.BooleanField(
        source="product.requires_prescription",
        read_only=True,
    )

    class Meta:
        model = CustomerCartItem
        fields = (
            "product_id",
            "name",
            "price",
            "image",
            "quantity",
            "special_instructions",
            "available",
            "requires_prescription",
        )

    def get_image(self, item):
        if not item.product.image:
            return ""
        request = self.context.get("request")
        url = item.product.image.url
        return request.build_absolute_uri(url) if request else url

    def get_available(self, item):
        return bool(item.product.in_stock and not item.product.requires_prescription)


class CustomerCartSerializer(serializers.ModelSerializer):
    store = serializers.SerializerMethodField()
    items = CustomerCartItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = CustomerCart
        fields = ("id", "store", "items", "subtotal", "updated_at")

    def get_store(self, cart):
        store = cart.store
        return {
            "id": str(store.id),
            "name": store.name,
            "is_open": bool(store.is_open and store.is_active),
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
            (item.product.price * item.quantity for item in cart.items.all()),
            Decimal("0.00"),
        )
        return str(total)
