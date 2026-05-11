from django.core.exceptions import ValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Ride, RideEvent, RideStatus
from .serializers import RideCreateSerializer, RideSerializer, RideStatusUpdateSerializer


class RideViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base = Ride.objects.select_related("rider", "passenger", "rider__user")
        if user.is_staff or user.is_superuser:
            return base
        rider_profile = getattr(user, "rider_profile", None)
        if rider_profile:
            return base.filter(rider=rider_profile)
        return base.filter(passenger=user)

    def get_serializer_class(self):
        if self.action == "create":
            return RideCreateSerializer
        return RideSerializer

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        ride = self.get_object()
        serializer = RideStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        try:
            self._enforce_transition_permissions(ride, new_status)
            ride.transition_to(new_status)
            if new_status == "CANCELLED":
                ride.cancelled_by = request.user
            ride.save()
            RideEvent.objects.create(
                ride=ride,
                event_type=f"STATUS_{new_status}",
                actor=request.user,
                payload={"status": new_status},
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RideSerializer(ride).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        return self._transition_with_status(request, pk, RideStatus.MATCHED)

    @action(detail=True, methods=["post"], url_path="arrive")
    def arrive(self, request, pk=None):
        return self._transition_with_status(request, pk, RideStatus.RIDER_ARRIVED)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        return self._transition_with_status(request, pk, RideStatus.IN_TRIP)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        return self._transition_with_status(request, pk, RideStatus.COMPLETED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        return self._transition_with_status(request, pk, RideStatus.CANCELLED)

    def _transition_with_status(self, request, pk, new_status: str):
        ride = self.get_object()
        try:
            self._enforce_transition_permissions(ride, new_status)
            ride.transition_to(new_status)
            if new_status == RideStatus.CANCELLED:
                ride.cancelled_by = request.user
            ride.save()
            RideEvent.objects.create(
                ride=ride,
                event_type=f"STATUS_{new_status}",
                actor=request.user,
                payload={"status": new_status},
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RideSerializer(ride).data, status=status.HTTP_200_OK)

    def _enforce_transition_permissions(self, ride, new_status: str) -> None:
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return
        if new_status == "CANCELLED":
            if ride.passenger_id != user.id and (not ride.rider or ride.rider.user_id != user.id):
                raise ValidationError("Only the passenger or assigned rider can cancel this ride.")
            return
        if new_status == "MATCHED":
            raise ValidationError("Only admin/system can set MATCHED.")
        if not ride.rider or ride.rider.user_id != user.id:
            raise ValidationError("Only the assigned rider can update this ride status.")
