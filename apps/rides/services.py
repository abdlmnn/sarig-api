from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from math import radians, cos, sin, asin, sqrt

from apps.riders.models import RiderProfile

from .models import FareBreakdown, Ride, RideStatus, VehicleType


class RideAssignmentService:
    @staticmethod
    def haversine_km(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return 6371 * c

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

    @classmethod
    def find_best_rider_for_ride(cls, ride: Ride):
        candidates = RiderProfile.objects.filter(
            is_online=True,
            is_available=True,
            can_do_ride_hailing=True,
            vehicle_type=ride.requested_vehicle_type,
            current_latitude__isnull=False,
            current_longitude__isnull=False,
        )
        best_rider = None
        min_distance = float("inf")
        pickup_lat = float(ride.pickup_lat)
        pickup_lng = float(ride.pickup_lng)
        max_radius = float(settings.JOYRIDE_MATCHING_MAX_RADIUS_KM)

        for rider in candidates:
            distance = cls.haversine_km(
                pickup_lng,
                pickup_lat,
                float(rider.current_longitude),
                float(rider.current_latitude),
            )
            if distance <= max_radius and distance < min_distance:
                min_distance = distance
                best_rider = rider
        return best_rider, min_distance if best_rider else None

    @classmethod
    def auto_assign_best_rider(cls, ride: Ride) -> Ride:
        if ride.status != RideStatus.REQUESTED or ride.rider_id:
            return ride
        rider, _distance = cls.find_best_rider_for_ride(ride)
        if not rider:
            return ride
        return cls.assign_rider(ride, rider)


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
