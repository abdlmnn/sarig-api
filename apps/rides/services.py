from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings

from apps.riders.models import RiderProfile

from .models import FareBreakdown, Ride, RideStatus, VehicleType


class RideAssignmentService:
    @staticmethod
    def assign_rider(ride: Ride, rider: RiderProfile) -> Ride:
        if ride.status != RideStatus.REQUESTED:
            raise ValidationError("Only REQUESTED rides can be assigned.")
        if not rider.is_online or not rider.is_available or not rider.can_do_ride_hailing:
            raise ValidationError("Rider is not eligible for ride-hailing assignment.")
        if rider.vehicle_type != ride.requested_vehicle_type:
            raise ValidationError("Rider vehicle type is not compatible with requested ride type.")

        ride.rider = rider
        ride.assigned_vehicle_type = rider.vehicle_type
        ride.transition_to(RideStatus.MATCHED)
        ride.save()
        rider.is_available = False
        rider.save(update_fields=["is_available"])
        return ride


class RideFareService:
    VEHICLE_RATES = {
        VehicleType.MOTORCYCLE: {"base": Decimal("50.00"), "per_km": Decimal("12.00"), "per_min": Decimal("2.00")},
        VehicleType.CAR: {"base": Decimal("80.00"), "per_km": Decimal("18.00"), "per_min": Decimal("3.00")},
    }

    @classmethod
    def _q(cls, amount: Decimal) -> Decimal:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_total(cls, vehicle_type: str, distance_km: Decimal, duration_min: Decimal) -> dict:
        rates = cls.VEHICLE_RATES[vehicle_type]
        base_fare = rates["base"]
        distance_fare = cls._q(rates["per_km"] * Decimal(distance_km))
        time_fare = cls._q(rates["per_min"] * Decimal(duration_min))
        surge_multiplier = Decimal(str(settings.JOYRIDE_SURGE_MULTIPLIER if settings.JOYRIDE_ENABLE_SURGE else "1.00"))
        subtotal = base_fare + distance_fare + time_fare
        total = cls._q(subtotal * surge_multiplier)
        return {
            "base_fare": cls._q(base_fare),
            "distance_fare": distance_fare,
            "time_fare": time_fare,
            "surge_multiplier": cls._q(surge_multiplier),
            "discount_amount": Decimal("0.00"),
            "total_fare": total,
        }

    @classmethod
    def upsert_breakdown(cls, ride: Ride, vehicle_type: str, distance_km: Decimal, duration_min: Decimal) -> FareBreakdown:
        fare_data = cls.calculate_total(vehicle_type, distance_km, duration_min)
        breakdown, _ = FareBreakdown.objects.update_or_create(
            ride=ride,
            defaults={"vehicle_type": vehicle_type, **fare_data},
        )
        ride.estimated_fare = fare_data["total_fare"]
        ride.save(update_fields=["estimated_fare", "updated_at"])
        return breakdown

    @classmethod
    def finalize_fare(cls, ride: Ride) -> FareBreakdown:
        vehicle_type = ride.assigned_vehicle_type or ride.requested_vehicle_type
        breakdown = cls.upsert_breakdown(ride, vehicle_type, ride.distance_km, ride.duration_min)
        ride.final_fare = breakdown.total_fare
        ride.save(update_fields=["final_fare", "updated_at"])
        return breakdown
