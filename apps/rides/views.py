from django.core.exceptions import ValidationError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Ride, RideEvent
from .serializers import RideCreateSerializer, RideSerializer, RideStatusUpdateSerializer


class RideViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Ride.objects.filter(passenger=user).select_related("rider", "passenger")

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
            ride.transition_to(new_status)
            ride.save(update_fields=["status", "updated_at"])
            RideEvent.objects.create(
                ride=ride,
                event_type=f"STATUS_{new_status}",
                actor=request.user,
                payload={"status": new_status},
            )
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RideSerializer(ride).data, status=status.HTTP_200_OK)

