from rest_framework import serializers
from .models import RiderOrderOffer, RiderOrderOfferStatus, RiderProfile, RiderTransaction

class RiderTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderTransaction
        fields = ["id", "order", "amount", "transaction_type", "description", "created_at"]

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
            .filter(rider=obj, status=RiderOrderOfferStatus.OFFERED)
            .order_by("expires_at")
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
            if not offer.is_expired()
        ]
