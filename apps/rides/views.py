from django.core.exceptions import ValidationError
import logging
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.riders.models import RiderProfile

from .models import Ride, RideEvent, RideStatus
from .realtime import publish_ride_event
from .serializers import RideAssignSerializer, RideCancelSerializer, RideCreateSerializer, RideSerializer, RideStatusUpdateSerializer
from .services import RideAssignmentService, RideFareService

logger = logging.getLogger(__name__)


class RideViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

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
        ride = self.get_object()
        user = request.user
        if not ride.rider or ride.rider.user_id != user.id:
            return Response({"detail": "Only assigned rider can accept this ride."}, status=status.HTTP_403_FORBIDDEN)
        if ride.status != RideStatus.MATCHED:
            return Response({"detail": "Ride must be MATCHED before rider acceptance."}, status=status.HTTP_400_BAD_REQUEST)
        if ride.rider_accepted_at:
            return Response(RideSerializer(ride).data, status=status.HTTP_200_OK)
        from django.utils import timezone
        ride.rider_accepted_at = timezone.now()
        ride.save(update_fields=["rider_accepted_at", "updated_at"])
        RideEvent.objects.create(
            ride=ride,
            event_type="RIDER_ACCEPTED",
            actor=user,
            payload={"status": ride.status},
        )
        try:
            publish_ride_event(ride, "RIDER_ACCEPTED", {"status": ride.status})
        except Exception as exc:
            logger.warning("Failed to publish RIDER_ACCEPTED event for ride %s: %s", ride.id, exc)
        return Response(RideSerializer(ride).data, status=status.HTTP_200_OK)

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
        serializer = RideCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._transition_with_status(
            request,
            pk,
            RideStatus.CANCELLED,
            extra_payload={"cancel_reason": serializer.validated_data.get("cancel_reason", "")},
        )

    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request, pk=None):
        ride = self.get_object()
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"detail": "Only admin/system can assign rides."}, status=status.HTTP_403_FORBIDDEN)

        # Idempotent behavior: same assignment request on already matched ride returns success.
        if ride.status == RideStatus.MATCHED and ride.rider_id:
            serializer = RideAssignSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            if ride.rider_id == serializer.validated_data["rider_id"]:
                return Response(RideSerializer(ride).data, status=status.HTTP_200_OK)

        serializer = RideAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rider = RiderProfile.objects.filter(id=serializer.validated_data["rider_id"]).select_related("user").first()
        if not rider:
            return Response({"detail": "Rider not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            ride = RideAssignmentService.assign_rider(ride, rider)
            RideEvent.objects.create(
                ride=ride,
                event_type="RIDE_ASSIGNED",
                actor=request.user,
                payload={"rider_id": str(rider.id), "status": ride.status},
            )
            try:
                publish_ride_event(ride, "RIDE_ASSIGNED", {"rider_id": str(rider.id), "status": ride.status})
            except Exception as exc:
                logger.warning("Failed to publish RIDE_ASSIGNED event for ride %s: %s", ride.id, exc)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RideSerializer(ride).data, status=status.HTTP_200_OK)

    def _transition_with_status(self, request, pk, new_status: str, extra_payload=None):
        ride = self.get_object()
        try:
            self._enforce_transition_permissions(ride, new_status)
            ride.transition_to(new_status)
            if new_status == RideStatus.CANCELLED:
                ride.cancelled_by = request.user
                ride.cancel_reason = (extra_payload or {}).get("cancel_reason", "")
                if ride.rider and ride.rider.user_id == request.user.id and ride.rider_accepted_at:
                    penalty = RideAssignmentService.apply_rider_cancel_penalty(ride)
                    (extra_payload := (extra_payload or {})).update({"rider_cancel_penalty": str(penalty)})
            ride.save()
            if new_status == RideStatus.COMPLETED:
                RideFareService.finalize_fare(ride)
            if new_status in {RideStatus.COMPLETED, RideStatus.CANCELLED} and ride.rider:
                ride.rider.is_available = True
                ride.rider.save(update_fields=["is_available"])
            RideEvent.objects.create(
                ride=ride,
                event_type=f"STATUS_{new_status}",
                actor=request.user,
                payload={"status": new_status, **(extra_payload or {})},
            )
            try:
                publish_ride_event(ride, f"STATUS_{new_status}", {"status": new_status, **(extra_payload or {})})
            except Exception as exc:
                logger.warning("Failed to publish %s event for ride %s: %s", new_status, ride.id, exc)
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
        if new_status in {RideStatus.RIDER_ARRIVED, RideStatus.IN_TRIP} and not ride.rider_accepted_at:
            raise ValidationError("Rider must accept the ride before continuing trip flow.")
