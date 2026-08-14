from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Min, Sum
from django.utils import timezone

from apps.marketing.models import PromoCode
from apps.onboarding.models import ApplicationStatus, MerchantApplication, RiderApplication
from apps.orders.models import Order, OrderStatus
from apps.payments.models import PaymentStatus, PaymentTransaction
from apps.reviews.models import OrderReview
from apps.riders.models import RiderProfile
from apps.rides.models import Ride, RideStatus
from apps.vendors.models import Store
from apps.users.geo import haversine_km

from .models import AdminAlert, LoadStatus, ServiceZone


MARAWI_CENTER = {
    "label": "Marawi City",
    "latitude": 8.0034,
    "longitude": 124.2839,
    "zoom": 13,
}

ACTIVE_ORDER_STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.ACCEPTED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
    OrderStatus.ON_THE_WAY,
]

ACTIVE_RIDE_STATUSES = [
    RideStatus.REQUESTED,
    RideStatus.MATCHED,
    RideStatus.RIDER_ARRIVED,
    RideStatus.IN_TRIP,
]


def envelope(data=None, message="Request successful", success=True, **extra):
    payload = {"success": success, "message": message}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return payload


def normalize_text(value):
    return " ".join(str(value or "").strip().lower().split())


def to_float(value):
    return float(value or Decimal("0.00"))


def percent_change(current, previous):
    current = Decimal(str(current or 0))
    previous = Decimal(str(previous or 0))
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round(float(((current - previous) / previous) * 100), 1)


def zone_aliases(zone):
    aliases = [zone.name, *(zone.barangay_names or [])]
    return {normalize_text(alias) for alias in aliases if normalize_text(alias)}


def zone_matches_barangay(zone, barangay):
    return normalize_text(barangay) in zone_aliases(zone)


def nearest_zone_for_point(lat, lng, zones, max_km=8):
    if lat is None or lng is None:
        return None
    best = None
    best_distance = None
    for zone in zones:
        distance = haversine_km(float(lng), float(lat), float(zone.center_longitude), float(zone.center_latitude))
        if best_distance is None or distance < best_distance:
            best = zone
            best_distance = distance
    return best if best is not None and best_distance is not None and best_distance <= max_km else None


def zone_for_store(store, zones):
    for zone in zones:
        if zone_matches_barangay(zone, store.barangay):
            return zone
    return nearest_zone_for_point(store.latitude, store.longitude, zones)


def zone_for_ride(ride, zones):
    return nearest_zone_for_point(ride.pickup_lat, ride.pickup_lng, zones)


def zone_for_rider(rider, zones):
    return nearest_zone_for_point(rider.current_latitude, rider.current_longitude, zones)


def calculate_load_status(active_orders, available_riders, average_delay_minutes):
    rider_ratio = active_orders / max(available_riders, 1)
    if average_delay_minutes >= 8 or rider_ratio >= 6:
        return LoadStatus.WATCH
    if rider_ratio >= 3:
        return LoadStatus.HIGH
    return LoadStatus.STABLE


def average_delay_minutes_for_orders(orders):
    now = timezone.now()
    delayed_minutes = []
    for order in orders:
        if order.estimated_arrival_time and order.estimated_arrival_time < now:
            delayed_minutes.append(int((now - order.estimated_arrival_time).total_seconds() // 60))
        elif order.status in [OrderStatus.PENDING, OrderStatus.ACCEPTED, OrderStatus.PREPARING]:
            age_minutes = int((now - order.created_at).total_seconds() // 60)
            if age_minutes > 30:
                delayed_minutes.append(age_minutes - 30)
    return int(sum(delayed_minutes) / len(delayed_minutes)) if delayed_minutes else 0


class ServiceZoneMetrics:
    def __init__(self, city="Marawi", include_inactive=False):
        zone_queryset = ServiceZone.objects.filter(city__iexact=city)
        if not include_inactive:
            zone_queryset = zone_queryset.filter(is_active=True)
        self.zones = list(zone_queryset.order_by("priority", "name"))
        self.stores = list(Store.objects.select_related("owner").filter(city__iexact=city))
        self.orders = list(Order.objects.select_related("store").filter(store__city__iexact=city))
        self.rides = list(Ride.objects.select_related("rider", "rider__user").all())
        self.riders = list(RiderProfile.objects.select_related("user").all())

    def metrics_by_zone(self):
        metrics = {
            zone.id: {
                "zone": zone,
                "stores": [],
                "orders": [],
                "rides": [],
                "riders": [],
            }
            for zone in self.zones
        }

        for store in self.stores:
            zone = zone_for_store(store, self.zones)
            if zone and zone.id in metrics:
                metrics[zone.id]["stores"].append(store)

        store_zone = {}
        for zone_id, group in metrics.items():
            for store in group["stores"]:
                store_zone[store.id] = zone_id

        for order in self.orders:
            zone_id = store_zone.get(order.store_id)
            if zone_id in metrics:
                metrics[zone_id]["orders"].append(order)

        for ride in self.rides:
            zone = zone_for_ride(ride, self.zones)
            if zone and zone.id in metrics:
                metrics[zone.id]["rides"].append(ride)

        for rider in self.riders:
            zone = zone_for_rider(rider, self.zones)
            if zone and zone.id in metrics:
                metrics[zone.id]["riders"].append(rider)

        return metrics

    def zone_payloads(self, status_filter=None):
        payloads = []
        for group in self.metrics_by_zone().values():
            zone = group["zone"]
            active_orders = [order for order in group["orders"] if order.status in ACTIVE_ORDER_STATUSES]
            active_rides = [ride for ride in group["rides"] if ride.status in ACTIVE_RIDE_STATUSES]
            active_riders = [rider for rider in group["riders"] if rider.is_online]
            available_riders = [rider for rider in active_riders if rider.is_available]
            approved_merchants = [store for store in group["stores"] if store.is_active]
            average_delay = average_delay_minutes_for_orders(active_orders)
            load_status = calculate_load_status(len(active_orders), len(available_riders), average_delay)

            if status_filter and load_status != status_filter:
                continue

            payloads.append(
                {
                    "id": str(zone.id),
                    "name": zone.name,
                    "slug": zone.slug,
                    "city": zone.city,
                    "province": zone.province,
                    "load_status": load_status,
                    "active_orders": len(active_orders),
                    "orders": len(active_orders),
                    "active_transport_bookings": len(active_rides),
                    "available_riders": len(available_riders),
                    "active_riders": len(active_riders),
                    "approved_merchants": len(approved_merchants),
                    "average_delay_minutes": average_delay,
                    "center_latitude": str(zone.center_latitude),
                    "center_longitude": str(zone.center_longitude),
                    "boundary": zone.boundary or None,
                    "last_updated_at": timezone.now().isoformat(),
                }
            )
        return payloads

    def list_payload(self, status_filter=None):
        zones = self.zone_payloads(status_filter=status_filter)
        return {
            "city": "Marawi",
            "updated_at": timezone.now().isoformat(),
            "map": {
                "center_latitude": str(MARAWI_CENTER["latitude"]),
                "center_longitude": str(MARAWI_CENTER["longitude"]),
                "zoom": MARAWI_CENTER["zoom"],
            },
            "summary": {
                "zones": len(zones),
                "active_orders": sum(zone["active_orders"] for zone in zones),
                "active_transport_bookings": sum(zone["active_transport_bookings"] for zone in zones),
                "available_riders": sum(zone["available_riders"] for zone in zones),
                "watch_zones": sum(1 for zone in zones if zone["load_status"] == LoadStatus.WATCH),
            },
            "zones": zones,
        }


def dashboard_stats(date_from=None, date_to=None):
    orders = Order.objects.all()
    rides = Ride.objects.all()
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
        rides = rides.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
        rides = rides.filter(created_at__date__lte=date_to)

    delivered_orders = orders.filter(status=OrderStatus.DELIVERED)
    gmv = delivered_orders.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    delivery_fees = delivered_orders.aggregate(total=Sum("delivery_fee"))["total"] or Decimal("0.00")
    system_fees = delivered_orders.aggregate(total=Sum("system_fee"))["total"] or Decimal("0.00")
    transport_fees = rides.filter(status=RideStatus.COMPLETED).aggregate(total=Sum("final_fare"))["total"] or Decimal("0.00")
    revenue = delivery_fees + system_fees + transport_fees

    return {
        "gmv": {"amount": to_float(gmv), "currency": "PHP", "change_percent": 0.0},
        "revenue": {"amount": to_float(revenue), "currency": "PHP", "change_percent": 0.0},
        "orders": {"total": orders.count(), "live": orders.filter(status__in=ACTIVE_ORDER_STATUSES).count()},
        "trips": {"total": rides.count(), "live": rides.filter(status__in=ACTIVE_RIDE_STATUSES).count()},
        "reviews": {"pending": 0},
    }


def onboarding_summary():
    today = timezone.localdate()
    return {
        "merchants": MerchantApplication.objects.exclude(status=ApplicationStatus.APPROVED).count(),
        "riders": RiderApplication.objects.exclude(status=ApplicationStatus.APPROVED).count(),
        "ready": MerchantApplication.objects.filter(status=ApplicationStatus.PENDING).count()
        + RiderApplication.objects.filter(status=ApplicationStatus.PENDING).count(),
        "changes_requested": MerchantApplication.objects.filter(status=ApplicationStatus.REQUEST_CHANGES).count()
        + RiderApplication.objects.filter(status=ApplicationStatus.REQUEST_CHANGES).count(),
        "approved_today": MerchantApplication.objects.filter(status=ApplicationStatus.APPROVED, updated_at__date=today).count()
        + RiderApplication.objects.filter(status=ApplicationStatus.APPROVED, updated_at__date=today).count(),
        "rejected_today": MerchantApplication.objects.filter(status=ApplicationStatus.REJECTED, updated_at__date=today).count()
        + RiderApplication.objects.filter(status=ApplicationStatus.REJECTED, updated_at__date=today).count(),
    }


def admin_dashboard_payload(date_from=None, date_to=None, zone_id=None):
    zone_metrics = ServiceZoneMetrics()
    zone_payloads = zone_metrics.zone_payloads()
    if zone_id:
        zone_payloads = [zone for zone in zone_payloads if zone["id"] == zone_id]

    summary = onboarding_summary()
    finance = finance_overview(date_from=date_from, date_to=date_to)
    marketing = marketing_overview()

    return {
        "stats": dashboard_stats(date_from=date_from, date_to=date_to),
        "service_zones": {
            "map_center": {
                "label": MARAWI_CENTER["label"],
                "latitude": MARAWI_CENTER["latitude"],
                "longitude": MARAWI_CENTER["longitude"],
            },
            "zones": [
                {
                    "id": zone["id"],
                    "name": zone["name"],
                    "orders": zone["active_orders"],
                    "active_riders": zone["active_riders"],
                    "average_delay_minutes": zone["average_delay_minutes"],
                    "load_status": zone["load_status"].lower(),
                }
                for zone in zone_payloads
            ],
        },
        "onboarding_summary": {
            "merchant_pending": MerchantApplication.objects.filter(status=ApplicationStatus.PENDING).count(),
            "merchant_ready": MerchantApplication.objects.filter(status=ApplicationStatus.UNDER_REVIEW).count(),
            "rider_pending": RiderApplication.objects.filter(status=ApplicationStatus.PENDING).count(),
            "rider_ready": RiderApplication.objects.filter(status=ApplicationStatus.UNDER_REVIEW).count(),
            "changes_requested": summary["changes_requested"],
            "approved_today": summary["approved_today"],
        },
        "latest_applications": latest_applications_payload(),
        "finance": {
            "revenue_streams": [
                {"label": "Merchant Fees", "amount": finance["merchant_fees"], "currency": "PHP", "share_percent": revenue_share(finance["merchant_fees"], finance["platform_revenue"])},
                {"label": "Delivery Fees", "amount": finance["delivery_fees"], "currency": "PHP", "share_percent": revenue_share(finance["delivery_fees"], finance["platform_revenue"])},
                {"label": "Transport Fees", "amount": finance["transport_fees"], "currency": "PHP", "share_percent": revenue_share(finance["transport_fees"], finance["platform_revenue"])},
            ]
        },
        "marketing": {
            "new_customers": marketing["new_customers"],
            "new_customers_delta": marketing["new_customers_delta"],
            "repeat_orders_percent": marketing["repeat_orders_percent"],
            "repeat_orders_change_percent": marketing["repeat_orders_change_percent"],
            "promo_spend": {"amount": marketing["promo_spend"], "currency": "PHP", "status": "active"},
        },
        "system_watch": [
            {"id": str(alert.id), "severity": alert.severity, "message": alert.message}
            for alert in AdminAlert.objects.filter(is_resolved=False).order_by("-created_at")[:4]
        ],
        "last_updated_at": timezone.now().isoformat(),
    }


def latest_applications_payload():
    def wait_minutes(app):
        return int((timezone.now() - app.created_at).total_seconds() // 60)

    merchants = MerchantApplication.objects.filter(
        status=ApplicationStatus.PENDING
    ).order_by("-created_at")[:4]
    riders = RiderApplication.objects.filter(
        status=ApplicationStatus.PENDING
    ).order_by("-created_at")[:4]
    return {
        "merchant": [
            {
                "id": app.application_id,
                "name": app.business_name,
                "status": app.status.lower(),
                "status_label": app.get_status_display(),
                "submitted_at": app.created_at,
                "wait_minutes": wait_minutes(app),
            }
            for app in merchants
        ],
        "rider": [
            {
                "id": app.application_id,
                "name": app.applicant_name,
                "status": app.status.lower(),
                "status_label": app.get_status_display(),
                "submitted_at": app.created_at,
                "wait_minutes": wait_minutes(app),
            }
            for app in riders
        ],
    }


def revenue_share(amount, total):
    total = Decimal(str(total or 0))
    amount = Decimal(str(amount or 0))
    if total == 0:
        return 0
    return int(round(float((amount / total) * 100)))


def finance_overview(date_from=None, date_to=None):
    orders = Order.objects.filter(status=OrderStatus.DELIVERED)
    rides = Ride.objects.filter(status=RideStatus.COMPLETED)
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
        rides = rides.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
        rides = rides.filter(created_at__date__lte=date_to)

    gmv = orders.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    merchant_fees = orders.aggregate(total=Sum("system_fee"))["total"] or Decimal("0.00")
    delivery_fees = orders.aggregate(total=Sum("delivery_fee"))["total"] or Decimal("0.00")
    transport_fees = rides.aggregate(total=Sum("final_fare"))["total"] or Decimal("0.00")
    pending_payments = PaymentTransaction.objects.filter(status__in=[PaymentStatus.PENDING, PaymentStatus.AUTHORIZED])
    platform_revenue = merchant_fees + delivery_fees + transport_fees

    return {
        "gmv": to_float(gmv),
        "platform_revenue": to_float(platform_revenue),
        "merchant_fees": to_float(merchant_fees),
        "delivery_fees": to_float(delivery_fees),
        "transport_fees": to_float(transport_fees),
        "pending_payouts_amount": to_float(pending_payments.aggregate(total=Sum("amount"))["total"]),
        "currency": "PHP",
    }


def marketing_overview():
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    previous_start = now - timedelta(days=60)
    customer_counts = (
        Order.objects.filter(created_at__gte=previous_start)
        .values("customer_id")
        .annotate(order_count=Count("id"), first_order_at=Min("created_at"))
    )
    new_customers = sum(1 for row in customer_counts if row["first_order_at"] >= thirty_days_ago)
    previous_new_customers = sum(1 for row in customer_counts if row["first_order_at"] < thirty_days_ago)
    total_customers = len(customer_counts)
    repeat_customers = sum(1 for row in customer_counts if row["order_count"] > 1)
    repeat_percent = int(round((repeat_customers / total_customers) * 100)) if total_customers else 0
    promo_spend = Order.objects.filter(created_at__gte=thirty_days_ago).aggregate(total=Sum("discount_amount"))["total"] or Decimal("0.00")

    return {
        "new_customers": new_customers,
        "new_customers_delta": new_customers - previous_new_customers,
        "repeat_orders_percent": repeat_percent,
        "repeat_orders_change_percent": 0.0,
        "promo_spend": to_float(promo_spend),
        "active_campaigns": 0,
        "active_promo_codes": PromoCode.objects.filter(is_active=True, start_date__lte=now, end_date__gte=now).count(),
        "currency": "PHP",
    }


def zone_merchants(zone):
    stores = []
    for store in Store.objects.select_related("owner", "vertical").filter(city__iexact=zone.city):
        if zone_for_store(store, [zone]) == zone:
            stores.append(store)
    return stores


def zone_riders(zone):
    riders = []
    for rider in RiderProfile.objects.select_related("user").all():
        if zone_for_rider(rider, [zone]) == zone:
            riders.append(rider)
    return riders
