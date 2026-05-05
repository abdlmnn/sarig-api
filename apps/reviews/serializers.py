from rest_framework import serializers
from .models import OrderReview

class OrderReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderReview
        fields = [
            "id", "order", "customer", "store", "store_rating", 
            "store_comment", "rider_profile", "rider_rating", 
            "rider_comment", "created_at"
        ]
        read_only_fields = ["id", "created_at"]
