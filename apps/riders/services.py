import logging
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import RiderOrderOffer, RiderOrderOfferStatus, RiderProfile
from apps.users.geo import get_lat_lng, haversine_km

logger = logging.getLogger(__name__)

class RiderDispatcherService:
    OFFER_TTL_SECONDS = 90
    PREDISPATCH_PREP_THRESHOLD_MINUTES = 10
    LOCATION_FRESHNESS_SECONDS = 120

    haversine = staticmethod(haversine_km)

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
            can_do_delivery=True,
            last_location_update__gte=timezone.now()
            - timedelta(seconds=cls.LOCATION_FRESHNESS_SECONDS),
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
    def find_best_rider_for_order(cls, order, max_radius_km=10):
        store_lat, store_lng = get_lat_lng(order.store, "latitude", "longitude")
        return cls.find_best_rider(store_lat, store_lng, max_radius_km=max_radius_km)

    @classmethod
    def expire_stale_offers(cls):
        now = timezone.now()
        return RiderOrderOffer.objects.filter(
            status=RiderOrderOfferStatus.OFFERED,
            expires_at__lte=now,
        ).update(status=RiderOrderOfferStatus.EXPIRED, responded_at=now)

    @classmethod
    def offer_order_to_best_rider(cls, order):
        """
        Offers a delivery to the nearest available rider without assigning it yet.
        """
        from apps.orders.models import DeliveryMethod, OrderStatus

        if order.delivery_method != DeliveryMethod.DELIVERY:
            return None
        if order.status not in [OrderStatus.PREPARING, OrderStatus.READY]:
            return None
        if order.rider_id:
            return None
        cls.expire_stale_offers()
        if cls.active_offer_for_order(order).exists():
            return cls.active_offer_for_order(order).first()

        if settings.RIDER_DISPATCH_ALL_ONLINE:
            offers = cls.offer_order_to_online_riders(order)
            return offers[0] if offers else None

        rider_profile, distance = cls.find_best_rider_for_order(order)
        if not rider_profile:
            logger.warning("No rider available to offer order %s", order.id)
            return None

        expires_at = timezone.now() + timedelta(seconds=cls.OFFER_TTL_SECONDS)
        offer = RiderOrderOffer.objects.create(
            order=order,
            rider=rider_profile,
            distance_km=Decimal(str(round(distance, 2))),
            expires_at=expires_at,
        )
        cls.notify_rider_delivery_offer(offer)
        logger.info(
            "Offered order %s to rider %s (%.2fkm)",
            order.id,
            rider_profile.user.username,
            distance,
        )
        return offer

    @classmethod
    def offer_order_to_online_riders(cls, order):
        """Creates temporary test offers for every eligible online rider."""
        store_lat, store_lng = get_lat_lng(order.store, "latitude", "longitude")
        expires_at = timezone.now() + timedelta(seconds=cls.OFFER_TTL_SECONDS)
        offers = []
        riders = RiderProfile.objects.filter(
            is_online=True,
            is_available=True,
            can_do_delivery=True,
        ).exclude(
            order_offers__status=RiderOrderOfferStatus.OFFERED,
        ).select_related("user")

        for rider in riders:
            distance = None
            if rider.current_latitude is not None and rider.current_longitude is not None:
                distance = cls.haversine(
                    float(store_lng),
                    float(store_lat),
                    float(rider.current_longitude),
                    float(rider.current_latitude),
                )
            offer = RiderOrderOffer.objects.create(
                order=order,
                rider=rider,
                distance_km=Decimal(str(round(distance, 2))) if distance is not None else None,
                expires_at=expires_at,
            )
            cls.notify_rider_delivery_offer(offer)
            offers.append(offer)

        if not offers:
            logger.warning("No online riders available to offer order %s", order.id)
        return offers

    @classmethod
    def accept_order_offer(cls, order, rider_user):
        """
        Assigns the order only after the offered rider accepts it.
        """
        from apps.orders.models import DeliveryMethod, Order, OrderStatus

        with transaction.atomic():
            try:
                rider_profile = RiderProfile.objects.select_for_update().get(user=rider_user)
            except RiderProfile.DoesNotExist:
                return False, "Rider profile was not found."

            locked_order = Order.objects.select_for_update().get(id=order.id)
            if locked_order.delivery_method != DeliveryMethod.DELIVERY:
                return False, "Pickup orders do not need a rider."
            if locked_order.status not in [OrderStatus.PREPARING, OrderStatus.READY]:
                return False, "This order is not ready for rider assignment."
            if locked_order.rider_id:
                if locked_order.rider_id == rider_user.id:
                    return True, "You are already assigned to this order."
                return False, "This order is already assigned to another rider."
            if not rider_profile.is_online or not rider_profile.is_available:
                return False, "You must be online and available to accept this delivery."
            if (
                Order.objects.filter(
                    rider=rider_user,
                    delivery_method=DeliveryMethod.DELIVERY,
                    status__in=[
                        OrderStatus.PREPARING,
                        OrderStatus.READY,
                        OrderStatus.ON_THE_WAY,
                    ],
                )
                .exclude(id=locked_order.id)
                .exists()
            ):
                return False, "You already have an active delivery."

            offer = (
                RiderOrderOffer.objects.select_for_update()
                .filter(
                    order=locked_order,
                    rider=rider_profile,
                    status=RiderOrderOfferStatus.OFFERED,
                )
                .first()
            )
            if not offer:
                return False, "No active delivery offer was found for this rider."

            now = timezone.now()
            if offer.expires_at <= now:
                offer.status = RiderOrderOfferStatus.EXPIRED
                offer.responded_at = now
                offer.save(update_fields=["status", "responded_at"])
                return False, "This delivery offer has expired."

            locked_order.rider = rider_user
            locked_order.save(update_fields=["rider", "updated_at"])
            offer.status = RiderOrderOfferStatus.ACCEPTED
            offer.accepted_at = now
            offer.responded_at = offer.accepted_at
            offer.save(update_fields=["status", "accepted_at", "responded_at"])
            (
                RiderOrderOffer.objects.filter(status=RiderOrderOfferStatus.OFFERED)
                .filter(Q(order=locked_order) | Q(rider=rider_profile))
                .exclude(id=offer.id)
                .update(status=RiderOrderOfferStatus.CANCELLED, responded_at=now)
            )
            rider_profile.is_available = False
            rider_profile.save(update_fields=["is_available"])

        cls.notify_rider_pickup_ready(locked_order)
        logger.info("Rider %s accepted order %s", rider_user.username, locked_order.id)
        return True, "Delivery accepted."

    @classmethod
    def decline_order_offer(cls, order, rider_user):
        try:
            rider_profile = rider_user.rider_profile
        except RiderProfile.DoesNotExist:
            return False, "Rider profile was not found."

        offer = cls.active_offer_for_order(order).filter(rider=rider_profile).first()
        if not offer:
            return False, "No active delivery offer was found for this rider."

        offer.status = RiderOrderOfferStatus.DECLINED
        offer.responded_at = timezone.now()
        offer.save(update_fields=["status", "responded_at"])
        return True, "Delivery offer declined."

    @classmethod
    def dispatch_ready_order(cls, order):
        """
        Guarantees a ready delivery has a rider, preferring accepted offers first.
        """
        from apps.orders.models import DeliveryMethod, OrderStatus

        if order.delivery_method != DeliveryMethod.DELIVERY or order.status != OrderStatus.READY:
            return False
        if order.rider_id:
            cls.notify_rider_pickup_ready(order)
            return True

        accepted_offer = RiderOrderOffer.objects.filter(
            order=order,
            status=RiderOrderOfferStatus.ACCEPTED,
        ).select_related("rider", "rider__user").first()
        if accepted_offer:
            order.rider = accepted_offer.rider.user
            order.save(update_fields=["rider", "updated_at"])
            accepted_offer.rider.is_available = False
            accepted_offer.rider.save(update_fields=["is_available"])
            cls.notify_rider_pickup_ready(order)
            return True

        offer = cls.offer_order_to_best_rider(order)
        if offer:
            return True

        return cls.assign_rider_to_order(order)

    @classmethod
    def assign_rider_to_order(cls, order):
        """
        Fallback direct assignment for ready delivery orders.
        """
        logger.info("Dispatching rider for order %s", order.id)

        rider_profile, distance = cls.find_best_rider_for_order(order)

        if rider_profile:
            order.rider = rider_profile.user
            order.save(update_fields=["rider", "updated_at"])

            rider_profile.is_available = False
            rider_profile.save(update_fields=["is_available"])

            logger.info(
                "Order %s assigned to rider %s (%.2fkm away)",
                order.id,
                rider_profile.user.username,
                distance,
            )

            cls.notify_rider_pickup_ready(order)
            return True

        logger.warning("No available riders found for order %s", order.id)
        return False

    @staticmethod
    def active_offer_for_order(order):
        return RiderOrderOffer.objects.filter(
            order=order,
            status=RiderOrderOfferStatus.OFFERED,
        )

    @classmethod
    def maybe_pre_dispatch_order(cls, order):
        from apps.orders.models import DeliveryMethod, OrderStatus

        if order.delivery_method != DeliveryMethod.DELIVERY or order.status != OrderStatus.PREPARING:
            return None
        prep_minutes = cls.estimate_order_prep_minutes(order)
        if (
            prep_minutes > cls.PREDISPATCH_PREP_THRESHOLD_MINUTES
            and not settings.RIDER_DISPATCH_ALL_ONLINE
        ):
            return None
        return cls.offer_order_to_best_rider(order)

    @staticmethod
    def estimate_order_prep_minutes(order):
        prep_times = []
        for item in order.items.select_related("product").all():
            value = getattr(item.product, "preparation_time_minutes", None)
            if value is not None:
                prep_times.append(int(value))
        return max(prep_times, default=10)

    @staticmethod
    def notify_rider_delivery_offer(offer):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from apps.users.notifications import PushNotificationService

        rider_user = offer.rider.user
        payload = {
            "type": "DELIVERY_OFFER",
            "order_id": str(offer.order_id),
            "store_name": offer.order.store.name,
            "distance_km": str(offer.distance_km) if offer.distance_km is not None else None,
            "expires_at": offer.expires_at.isoformat(),
        }
        PushNotificationService.notify_rider_delivery_offer(rider_user, offer.order)

        try:
            async_to_sync(get_channel_layer().group_send)(
                f"rider_{rider_user.id}",
                {"type": "delivery_offer", "data": payload},
            )
        except Exception as exc:
            logger.warning("Failed to send rider offer websocket for order %s: %s", offer.order_id, exc)

    @staticmethod
    def notify_rider_pickup_ready(order):
        if not order.rider_id:
            return False
        from apps.users.notifications import PushNotificationService

        return PushNotificationService.notify_rider_pickup_ready(order.rider, order)

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
        
        logger.info("Rider %s earned %s for order %s", rider_profile.user.username, total_pay, order.id)
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
