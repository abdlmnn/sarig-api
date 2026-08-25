from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers
from django.utils import timezone
from apps.orders.models import Order, OrderStatus
from .models import RiderOrderOffer, RiderOrderOfferStatus, RiderProfile, RiderTransaction


class RiderLocationUpdateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(
        max_digits=None,
        decimal_places=None,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
    )
    longitude = serializers.DecimalField(
        max_digits=None,
        decimal_places=None,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
    )

    def validate(self, attrs):
        precision = Decimal("0.000001")
        attrs["latitude"] = attrs["latitude"].quantize(precision, rounding=ROUND_HALF_UP)
        attrs["longitude"] = attrs["longitude"].quantize(precision, rounding=ROUND_HALF_UP)
        return attrs


class RiderStatusUpdateSerializer(serializers.Serializer):
    is_online = serializers.BooleanField(required=False)


class RiderTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderTransaction
        fields = ["id", "order", "amount", "transaction_type", "description", "created_at"]


class RiderActiveOrderSerializer(serializers.ModelSerializer):
    order_id = serializers.UUIDField(source="id", read_only=True)
    display_id = serializers.SerializerMethodField()
    store = serializers.SerializerMethodField()
    destination = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()
    should_publish_location = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "order_id",
            "display_id",
            "status",
            "store",
            "destination",
            "estimated_arrival_time",
            "available_actions",
            "should_publish_location",
        ]

    def get_display_id(self, order):
        return f"SRG-{str(order.id)[:8].upper()}"

    def get_store(self, order):
        return {
            "name": order.store.name,
            "address_text": order.store.pinned_address or order.store.street_address,
            "latitude": str(order.store.latitude),
            "longitude": str(order.store.longitude),
        }

    def get_destination(self, order):
        return {
            "address_text": order.delivery_address_text,
            "latitude": str(order.delivery_latitude),
            "longitude": str(order.delivery_longitude),
        }

    def get_available_actions(self, order):
        if order.status == OrderStatus.READY:
            return ["pickup"]
        if order.status == OrderStatus.ON_THE_WAY:
            return ["delivered"]
        return []

    def get_should_publish_location(self, order):
        profile = getattr(order.rider, "rider_profile", None)
        return bool(profile and profile.is_online)


class RiderProfileSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")
    transactions = RiderTransactionSerializer(many=True, read_only=True)
    delivery_offers = serializers.SerializerMethodField()

    class Meta:
        model = RiderProfile
        fields = [
            "username",
            "is_online",
            "is_available",
            "balance",
            "vehicle_type",
            "delivery_offers",
            "transactions",
        ]

    def get_delivery_offers(self, obj):
        offers = (
            RiderOrderOffer.objects.select_related("order", "order__store")
            .filter(
                rider=obj,
                status=RiderOrderOfferStatus.OFFERED,
                expires_at__gt=timezone.now(),
            )
            .order_by("expires_at")
            [:1]
        )
        return [
            {
                "id": str(offer.id),
                "order_id": str(offer.order_id),
                "store_name": offer.order.store.name,
                "distance_km": str(offer.distance_km) if offer.distance_km is not None else None,
                "expires_at": offer.expires_at,
            }
            for offer in offers
        ]
