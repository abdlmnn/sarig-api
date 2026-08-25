from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.orders.models import DeliveryMethod, Order, OrderStatus
from apps.payments.models import PaymentMethod, PaymentStatus, PaymentTransaction
from apps.users.permissions import IsRider
from .models import RiderProfile
from .serializers import (
    RiderActiveOrderSerializer,
    RiderLocationUpdateSerializer,
    RiderProfileSerializer,
    RiderStatusUpdateSerializer,
)


ACTIVE_DELIVERY_STATUSES = [
    OrderStatus.PREPARING,
    OrderStatus.READY,
    OrderStatus.ON_THE_WAY,
]


def active_order_payload(user):
    order = (
        Order.objects.select_related("store", "rider__rider_profile")
        .filter(
            rider=user,
            delivery_method=DeliveryMethod.DELIVERY,
            status__in=ACTIVE_DELIVERY_STATUSES,
        )
        .order_by("created_at", "id")
        .first()
    )
    return RiderActiveOrderSerializer(order).data if order else None


class RiderStatusToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRider]

    def post(self, request):
        user = request.user
        serializer = RiderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile, _ = RiderProfile.objects.get_or_create(user=user)
        profile.is_online = serializer.validated_data.get("is_online", not profile.is_online)
        profile.save(update_fields=["is_online"])

        return Response({
            "is_online": profile.is_online,
            "message": f"You are now {'Online' if profile.is_online else 'Offline'}."
        })

class RiderLocationUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRider]

    def post(self, request):
        user = request.user

        serializer = RiderLocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lat = serializer.validated_data["latitude"]
        lng = serializer.validated_data["longitude"]

        profile = get_object_or_404(RiderProfile, user=user)
        profile.current_latitude = lat
        profile.current_longitude = lng
        profile.save()
        lat = profile.current_latitude
        lng = profile.current_longitude
        last_updated_at = profile.last_location_update.isoformat()

        # Broadcast to active order tracking group if on a delivery
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
                    "last_updated_at": last_updated_at,
                }
            )
        else:
            from .services import RiderDispatcherService

            waiting_order = (
                Order.objects.filter(
                    rider__isnull=True,
                    delivery_method=DeliveryMethod.DELIVERY,
                    status=OrderStatus.READY,
                )
                .order_by("created_at", "id")
                .first()
            )
            if waiting_order:
                RiderDispatcherService.dispatch_ready_order(waiting_order)

        return Response(
            {
                "status": "Location updated",
                "location": {
                    "latitude": str(lat),
                    "longitude": str(lng),
                    "last_updated_at": last_updated_at,
                },
            }
        )


class RiderOrderActionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRider]

    def post(self, request, order_id):
        action = request.data.get("action")
        order = get_object_or_404(Order, id=order_id)
        user = request.user

        if action == "accept_offer":
            from .services import RiderDispatcherService
            accepted, message = RiderDispatcherService.accept_order_offer(order, user)
            if not accepted:
                return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)
            order.broadcast_status_update()
            return Response({"status": "success", "message": message, "active_order": active_order_payload(user)})

        if action == "decline_offer":
            from .services import RiderDispatcherService
            declined, message = RiderDispatcherService.decline_order_offer(order, user)
            if not declined:
                return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"status": "success", "message": message})

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

            return Response({
                "status": "success",
                "message": "Order picked up. You are now on the way!",
                "active_order": active_order_payload(user),
            })

        elif action == "delivered":
            if order.status != OrderStatus.ON_THE_WAY:
                return Response(
                    {"error": "Order must be 'On the way' before completing delivery."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from .services import RiderDispatcherService

            with transaction.atomic():
                order.status = OrderStatus.DELIVERED
                order.save(update_fields=["status", "updated_at"])
                PaymentTransaction.objects.filter(
                    order=order,
                    payment_method=PaymentMethod.COD,
                    status=PaymentStatus.PENDING,
                ).update(status=PaymentStatus.SUCCESS, updated_at=timezone.now())
                RiderDispatcherService.record_delivery_earnings(order)

                profile = user.rider_profile
                profile.is_available = True
                profile.save(update_fields=["is_available"])

            order.broadcast_status_update()

            # Notify Customer
            from apps.users.notifications import PushNotificationService
            PushNotificationService.notify_order_status(order.customer, "DELIVERED", order.id)

            return Response({
                "status": "success",
                "message": "Order delivered! You are now available for new orders.",
                "active_order": active_order_payload(user),
            })

        return Response({"error": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)


class RiderDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRider]

    def get(self, request):
        user = request.user
        profile = get_object_or_404(RiderProfile, user=user)
        data = RiderProfileSerializer(profile).data
        data["active_order"] = active_order_payload(user)

        return Response(data)
