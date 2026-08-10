from rest_framework import serializers
from apps.common.validators import validate_image_upload
from .models import Category, CategoryTemplate, InventoryMode, MedicineReference, Product, ProductReference, ProductType, ModifierGroup, ModifierItem


class ModifierItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModifierItem
        fields = ["id", "linked_product", "name", "extra_price", "is_available"]


class ModifierGroupSerializer(serializers.ModelSerializer):
    items = ModifierItemSerializer(many=True, read_only=True)

    class Meta:
        model = ModifierGroup
        fields = ["id", "name", "is_required", "max_selections", "items"]


class MedicineReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicineReference
        fields = [
            "id",
            "registration_number",
            "product_information",
            "generic_name",
            "brand_name",
            "dosage_strength",
            "dosage_form",
            "classification",
            "pharmacologic_category",
            "packaging",
            "manufacturer",
            "country_of_origin",
            "trader",
            "importer",
            "distributor",
            "expiry_date",
            "requires_prescription",
            "is_active",
            "source",
        ]


class CategoryTemplateSerializer(serializers.ModelSerializer):
    vertical = serializers.SerializerMethodField()

    class Meta:
        model = CategoryTemplate
        fields = [
            "id",
            "vertical",
            "name",
            "slug",
            "description",
            "order",
            "is_active",
        ]

    def get_vertical(self, obj):
        return {
            "id": str(obj.vertical_id),
            "name": obj.vertical.name,
            "slug": obj.vertical.slug,
        }


class ProductReferenceSerializer(serializers.ModelSerializer):
    vertical = serializers.SerializerMethodField()

    class Meta:
        model = ProductReference
        fields = [
            "id",
            "vertical",
            "name",
            "brand_name",
            "barcode",
            "description",
            "product_type",
            "unit_type",
            "is_active",
            "source",
        ]

    def get_vertical(self, obj):
        return {
            "id": str(obj.vertical_id),
            "name": obj.vertical.name,
            "slug": obj.vertical.slug,
        }


class ProductSerializer(serializers.ModelSerializer):
    modifier_groups = ModifierGroupSerializer(many=True, read_only=True)
    in_stock = serializers.ReadOnlyField()
    medicine_reference_detail = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "name",
            "slug",
            "sku",
            "description",
            "price",
            "image",
            "product_type",
            "medicine_reference",
            "medicine_reference_detail",
            "unit_type",
            "requires_prescription",
            "generic_name",
            "brand_name",
            "dosage",
            "medicine_form",
            "preparation_time_minutes",
            "inventory_mode",
            "is_available",
            "track_inventory",
            "stock_quantity",
            "low_stock_threshold",
            "in_stock",
            "is_active",
            "modifier_groups",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_medicine_reference_detail(self, obj):
        if not obj.medicine_reference_id:
            return None
        return MedicineReferenceSerializer(obj.medicine_reference).data

    def validate_image(self, value):
        validate_image_upload(value)
        return value

    def validate(self, attrs):
        product_type = attrs.get("product_type", getattr(self.instance, "product_type", ProductType.GENERAL))
        inventory_mode = attrs.get("inventory_mode", getattr(self.instance, "inventory_mode", InventoryMode.NONE))
        stock_quantity = attrs.get("stock_quantity", getattr(self.instance, "stock_quantity", None))
        low_stock_threshold = attrs.get(
            "low_stock_threshold",
            getattr(self.instance, "low_stock_threshold", 5),
        )
        requires_prescription = attrs.get(
            "requires_prescription",
            getattr(self.instance, "requires_prescription", False),
        )

        if product_type != ProductType.MEDICINE and requires_prescription:
            raise serializers.ValidationError(
                {"requires_prescription": "Only medicine products can require a prescription."}
            )
        medicine_reference = attrs.get("medicine_reference", getattr(self.instance, "medicine_reference", None))
        if medicine_reference and product_type != ProductType.MEDICINE:
            raise serializers.ValidationError(
                {"medicine_reference": "Only medicine products can use a medicine reference."}
            )
        category = attrs.get("category", getattr(self.instance, "category", None))
        if category and category.store and category.store.vertical:
            allowed_product_types = category.store.vertical.allowed_product_types or []
            if allowed_product_types and product_type not in allowed_product_types:
                raise serializers.ValidationError(
                    {
                        "product_type": (
                            f"{product_type} products are not allowed for "
                            f"{category.store.vertical.name} stores."
                        )
                    }
                )
        if inventory_mode == InventoryMode.SIMPLE_STOCK and stock_quantity is None:
            raise serializers.ValidationError(
                {"stock_quantity": "Stock quantity is required when inventory_mode is simple_stock."}
            )
        if low_stock_threshold is None or low_stock_threshold < 0:
            raise serializers.ValidationError(
                {"low_stock_threshold": "Low stock threshold must be 0 or higher."}
            )
        if inventory_mode == InventoryMode.NONE:
            attrs["stock_quantity"] = None
        if medicine_reference:
            attrs.setdefault("generic_name", medicine_reference.generic_name)
            attrs.setdefault("brand_name", medicine_reference.brand_name)
            attrs.setdefault("dosage", medicine_reference.dosage_strength)
            attrs.setdefault("medicine_form", medicine_reference.dosage_form)
            attrs.setdefault("requires_prescription", medicine_reference.requires_prescription)
        return attrs
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
