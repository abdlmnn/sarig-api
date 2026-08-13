from rest_framework import serializers

from .models import DiscountType, PromoCode


class AvailablePromoCodeSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    detail = serializers.SerializerMethodField()

    class Meta:
        model = PromoCode
        fields = [
            "id",
            "code",
            "title",
            "detail",
            "discount_type",
            "discount_value",
            "min_order_amount",
            "max_discount_amount",
            "end_date",
        ]

    def get_title(self, promo):
        if promo.discount_type == DiscountType.PERCENTAGE:
            return f"{format_decimal(promo.discount_value)}% off"
        return f"Save ₱{format_decimal(promo.discount_value)}"

    def get_detail(self, promo):
        if promo.min_order_amount:
            return f"Min. order ₱{format_decimal(promo.min_order_amount)}"
        return "Available for this order"


def format_decimal(value):
    return f"{value:,.2f}".rstrip("0").rstrip(".")
