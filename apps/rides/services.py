from django.core.exceptions import ValidationError

from apps.riders.models import RiderProfile

from .models import Ride, RideStatus


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
        return ride

