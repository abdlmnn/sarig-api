from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.orders.models import Order, OrderStatus
from .models import OrderReview
from .serializers import OrderReviewSerializer

class SubmitReviewView(generics.CreateAPIView):
    serializer_class = OrderReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        order_id = request.data.get("order")
        order = get_object_or_404(Order, id=order_id)
        
        # 1. Security Check: Only the customer who placed the order can review it
        if order.customer != request.user:
            return Response(
                {"error": "You can only review your own orders."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # 2. Lifecycle Check: Only delivered orders can be reviewed
        if order.status != OrderStatus.DELIVERED:
            return Response(
                {"error": "You can only review delivered orders."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 3. Uniqueness Check: Only one review per order
        if hasattr(order, 'review'):
            return Response(
                {"error": "You have already reviewed this order."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Add extra context to data
        data = request.data.copy()
        data['customer'] = request.user.id
        data['store'] = order.store.id
        if order.rider:
            from apps.riders.models import RiderProfile
            try:
                rider_profile = order.rider.rider_profile
                data['rider_profile'] = rider_profile.id
            except:
                pass

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
