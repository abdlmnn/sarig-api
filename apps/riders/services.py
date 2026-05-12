import logging
from decimal import Decimal
from math import radians, cos, sin, asin, sqrt
from django.db.models import Q
from .models import RiderProfile
from apps.users.geo import get_lat_lng

logger = logging.getLogger(__name__)

class RiderDispatcherService:
    @staticmethod
    def haversine(lon1, lat1, lon2, lat2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        """
        # convert decimal degrees to radians 
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # haversine formula 
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        r = 6371 # Radius of earth in kilometers. Use 3956 for miles
        return c * r

    @classmethod
    def find_best_rider(cls, store_lat, store_lng, max_radius_km=10):
        """
        Finds the nearest online and available rider within a radius.
        Only finds riders capable of 'DELIVERY' or 'BOTH'.
        """
        # 1. Get all online and available riders with Delivery capabilities
        available_riders = RiderProfile.objects.filter(
            is_online=True,
            is_available=True,
            current_latitude__isnull=False,
            current_longitude__isnull=False,
            can_do_delivery=True
        )

        best_rider = None
        min_distance = float('inf')

        for rider in available_riders:
            distance = cls.haversine(
                float(store_lng), float(store_lat),
                float(rider.current_longitude), float(rider.current_latitude)
            )

            if distance <= max_radius_km and distance < min_distance:
                min_distance = distance
                best_rider = rider

        return best_rider, min_distance

    @classmethod
    def assign_rider_to_order(cls, order):
        """
        Orchestrates the dispatch for a specific order.
        """
        logger.info(f"Dispatching rider for order {order.id}")
        
        store_lat, store_lng = get_lat_lng(order.store, "latitude", "longitude")
        rider_profile, distance = cls.find_best_rider(store_lat, store_lng)

        if rider_profile:
            order.rider = rider_profile.user
            order.save()
            
            # Mark rider as busy
            rider_profile.is_available = False
            rider_profile.save()

            logger.info(f"Order {order.id} assigned to rider {rider_profile.user.username} ({distance:.2f}km away)")
            
            # TODO: Trigger real-time notification to Rider ("New delivery for you!")
            return True
        
        logger.warning(f"No available riders found for order {order.id}")
        return False

    @classmethod
    def record_delivery_earnings(cls, order):
        """
        Calculates and credits the rider's pay for a completed delivery.
        Uses F() expressions to prevent race conditions.
        """
        from django.db import transaction
        from django.db.models import F
        from .models import RiderTransaction
        
        rider_profile = order.rider.rider_profile
        
        # Calculate distance between store and customer
        store_lat, store_lng = get_lat_lng(order.store, "latitude", "longitude")
        distance = cls.haversine(
            float(store_lng), float(store_lat),
            float(order.delivery_longitude), float(order.delivery_latitude)
        )
        
        base_pay = Decimal("40.00")
        distance_pay = Decimal(str(round(distance * 10, 2)))
        total_pay = base_pay + distance_pay
        
        with transaction.atomic():
            # 1. Update Rider Balance Atomically (F expression prevents race conditions)
            RiderProfile.objects.filter(id=rider_profile.id).update(
                balance=F('balance') + total_pay
            )
            
            # 2. Record Transaction
            RiderTransaction.objects.create(
                rider=rider_profile,
                order=order,
                amount=total_pay,
                transaction_type="EARNING",
                description=f"Earning for Order #{str(order.id)[:8]} ({distance:.2f}km)"
            )
        
        logger.info(f"Rider {rider_profile.user.username} earned ₱{total_pay} for order {order.id}")
        return total_pay

    @classmethod
    def calculate_eta(cls, current_lat, current_lng, target_lat, target_lng):
        """
        Calculates a realistic ETA in minutes.
        Accounts for road distance (1.3x multiplier) and traffic.
        """
        # 1. Get straight-line distance
        base_distance = cls.haversine(
            float(current_lng), float(current_lat),
            float(target_lng), float(target_lat)
        )
        
        # 2. Road Factor (Roads aren't straight lines)
        road_distance = base_distance * 1.3
        
        # 3. Average Speed (30 km/h for urban motorcycle delivery)
        travel_time_minutes = (road_distance / 30) * 60
        
        # 4. Buffer for traffic/parking/handoff
        total_eta_minutes = round(travel_time_minutes + 5)
        
        return total_eta_minutes, round(road_distance, 2)

    @classmethod
    def update_order_eta(cls, order, rider_lat, rider_lng):
        """
        Updates the order's estimated arrival time based on rider's current location.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        eta_minutes, distance = cls.calculate_eta(
            rider_lat, rider_lng,
            order.delivery_latitude, order.delivery_longitude
        )
        
        order.estimated_arrival_time = timezone.now() + timedelta(minutes=eta_minutes)
        order.save()
        
        return eta_minutes, distance
