from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.orders.models import Order
from .models import ChatMessage
from .serializers import ChatMessageSerializer

class ChatHistoryView(generics.ListAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        order_id = self.kwargs.get("order_id")
        order = get_object_or_404(Order, id=order_id)
        
        # Security: Only Customer or Rider of this order can see history
        if self.request.user != order.customer and self.request.user != order.rider:
            return ChatMessage.objects.none()
            
        return ChatMessage.objects.filter(order=order)

    def list(self, request, *args, **kwargs):
        # We need the order object again to figure out who the "other person" is
        order_id = self.kwargs.get("order_id")
        order = get_object_or_404(Order, id=order_id)
        
        # Check security (if none, it will return empty list but we also want to block contact info)
        if request.user != order.customer and request.user != order.rider:
            return Response({"error": "Unauthorized access to chat."}, status=status.HTTP_403_FORBIDDEN)

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        # Determine the contact info based on who is asking
        contact_name = None
        contact_phone = None
        
        if request.user == order.customer:
            # If Customer is asking, give them the Rider's phone number
            if order.rider:
                contact_name = order.rider.get_full_name() or order.rider.username
                contact_phone = order.rider.phone_number
            else:
                contact_name = "Waiting for Rider"
                contact_phone = None
        elif request.user == order.rider:
            # If Rider is asking, give them the Customer's phone number
            contact_name = order.customer.get_full_name() or order.customer.username
            contact_phone = order.customer.phone_number
            
        return Response({
            "contact_info": {
                "name": contact_name,
                "phone_number": contact_phone
            },
            "messages": serializer.data
        })
