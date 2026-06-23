from rest_framework import serializers
from apps.common.validators import validate_image_upload
from .models import Category, Product, ModifierGroup, ModifierItem


class ModifierItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModifierItem
        fields = ["id", "name", "extra_price", "is_available"]


class ModifierGroupSerializer(serializers.ModelSerializer):
    items = ModifierItemSerializer(many=True, read_only=True)

    class Meta:
        model = ModifierGroup
        fields = ["id", "name", "is_required", "max_selections", "items"]


class ProductSerializer(serializers.ModelSerializer):
    modifier_groups = ModifierGroupSerializer(many=True, read_only=True)
    in_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "name",
            "slug",
            "description",
            "price",
            "image",
            "is_available",
            "track_inventory",
            "stock_quantity",
            "in_stock",
            "is_active",
            "modifier_groups",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_image(self, value):
        validate_image_upload(value)
        return value


class CategorySerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "store",
            "name",
            "slug",
            "description",
            "image",
            "is_active",
            "order",
            "products",
        ]
        read_only_fields = ["id"]

    def validate_image(self, value):
        validate_image_upload(value)
        return value
