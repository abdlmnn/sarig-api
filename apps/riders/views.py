from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import RiderProfile

class RiderStatusToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        
        # Security: Only users with 'rider' role can do this
        if not user.roles.filter(name="Rider").exists():
            return Response({"error": "Only riders can toggle status."}, status=status.HTTP_403_FORBIDDEN)
        
        profile, created = RiderProfile.objects.get_or_create(user=user)
        profile.is_online = not profile.is_online
        profile.save()

        return Response({
            "is_online": profile.is_online,
            "message": f"You are now {'Online' if profile.is_online else 'Offline'}."
        })

class RiderLocationUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        lat = request.data.get("latitude")
        lng = request.data.get("longitude")

        if not lat or not lng:
            return Response({"error": "Latitude and longitude are required."}, status=400)

        profile = get_object_or_404(RiderProfile, user=user)
        profile.current_latitude = lat
        profile.current_longitude = lng
        profile.save()

        # Broadcast to active order tracking group if on a delivery
        from apps.orders.models import Order, OrderStatus
        active_order = Order.objects.filter(rider=user, status=OrderStatus.ON_THE_WAY).first()
        
        if active_order:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from .services import RiderDispatcherService
            
            # Recalculate ETA in real-time
            eta_minutes, road_distance = RiderDispatcherService.update_order_eta(
                active_order, lat, lng
            )

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"order_{active_order.id}",
                {
                    "type": "location_update",
                    "latitude": str(lat),
                    "longitude": str(lng),
                    "remaining_minutes": eta_minutes,
                    "distance_km": road_distance,
                }
            )

        return Response({"status": "Location updated"})


class RiderOrderActionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        from apps.orders.models import Order, OrderStatus
        
        action = request.data.get("action")
        order = get_object_or_404(Order, id=order_id)
        user = request.user

        # 1. Security: Is this the rider assigned to this order?
        if order.rider != user:
            return Response(
                {"error": "You are not the rider assigned to this order."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. Logic Check
        if action == "pickup":
            if order.status != OrderStatus.READY:
                return Response(
                    {"error": "Order must be 'Ready for Pickup' before you can pick it up."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order.status = OrderStatus.ON_THE_WAY
            order.save()
            order.broadcast_status_update()

            # Notify Customer
            from apps.users.notifications import PushNotificationService
            PushNotificationService.notify_order_status(order.customer, "ON_THE_WAY", order.id)

            return Response({"status": "success", "message": "Order picked up. You are now on the way!"})

        elif action == "delivered":
            if order.status != OrderStatus.ON_THE_WAY:
                return Response(
                    {"error": "Order must be 'On the way' before completing delivery."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order.status = OrderStatus.DELIVERED
            order.save()
            order.broadcast_status_update()

            # Notify Customer
            from apps.users.notifications import PushNotificationService
            PushNotificationService.notify_order_status(order.customer, "DELIVERED", order.id)

            # Process Earnings
            from .services import RiderDispatcherService
            earnings = RiderDispatcherService.record_delivery_earnings(order)

            # Make rider available again
            profile = user.rider_profile
            profile.is_available = True
            profile.save()

            return Response({"status": "success", "message": "Order delivered! You are now available for new orders."})

        return Response({"error": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)


class RiderDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = get_object_or_404(RiderProfile, user=user)
        
        from .serializers import RiderProfileSerializer
        serializer = RiderProfileSerializer(profile)
        
        return Response(serializer.data)
