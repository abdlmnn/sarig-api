import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.riders.models import RiderProfile


class RideStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    MATCHED = "MATCHED", "Matched"
    RIDER_ARRIVED = "RIDER_ARRIVED", "Rider Arrived"
    IN_TRIP = "IN_TRIP", "In Trip"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    EXPIRED = "EXPIRED", "Expired"


class VehicleType(models.TextChoices):
    MOTORCYCLE = "MOTORCYCLE", "Motorcycle"
    CAR = "CAR", "Car"


ALLOWED_TRANSITIONS = {
    RideStatus.REQUESTED: {RideStatus.MATCHED, RideStatus.CANCELLED, RideStatus.EXPIRED},
    RideStatus.MATCHED: {RideStatus.RIDER_ARRIVED, RideStatus.CANCELLED},
    RideStatus.RIDER_ARRIVED: {RideStatus.IN_TRIP, RideStatus.CANCELLED},
    RideStatus.IN_TRIP: {RideStatus.COMPLETED},
    RideStatus.COMPLETED: set(),
    RideStatus.CANCELLED: set(),
    RideStatus.EXPIRED: set(),
}


class Ride(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    passenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rides")
    rider = models.ForeignKey(RiderProfile, null=True, blank=True, on_delete=models.PROTECT, related_name="rides")
    status = models.CharField(max_length=32, choices=RideStatus.choices, default=RideStatus.REQUESTED, db_index=True)
    requested_vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    assigned_vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, null=True, blank=True)
    pickup_lat = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_lng = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_lat = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_lng = models.DecimalField(max_digits=9, decimal_places=6)
    estimated_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    duration_min = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    cancel_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cancelled_rides")
    requested_at = models.DateTimeField(auto_now_add=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    rider_accepted_at = models.DateTimeField(null=True, blank=True)
    rider_cancel_penalty = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["requested_vehicle_type", "status"]),
        ]

    def transition_to(self, new_status: str) -> None:
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValidationError(f"Invalid transition from {self.status} to {new_status}.")
        self.status = new_status
        now = timezone.now()
        if new_status == RideStatus.MATCHED:
            self.matched_at = now
        elif new_status == RideStatus.IN_TRIP:
            self.started_at = now
        elif new_status == RideStatus.COMPLETED:
            self.completed_at = now
        elif new_status == RideStatus.CANCELLED:
            self.cancelled_at = now


class RideEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="ride_events")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class FareBreakdown(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ride = models.OneToOneField(Ride, on_delete=models.CASCADE, related_name="fare_breakdown")
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    distance_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    time_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    surge_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
