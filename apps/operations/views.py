from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order, OrderStatus
from apps.riders.models import RiderProfile
from apps.rides.models import Ride, RideStatus
from apps.vendors.models import Store
from apps.vendors.models import StoreManualOverride

from .models import AdminAlert, ServiceZone
from .serializers import AdminMerchantActionSerializer, AdminRiderActionSerializer
from .services import (
    ACTIVE_ORDER_STATUSES,
    ACTIVE_RIDE_STATUSES,
    ServiceZoneMetrics,
    admin_dashboard_payload,
    envelope,
    finance_overview,
    marketing_overview,
    zone_for_rider,
    zone_for_store,
    zone_merchants,
    zone_riders,
)


def parse_bool(value):
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def pagination_payload(items, page, page_size):
    paginator = Paginator(items, page_size)
    page_obj = paginator.get_page(page)
    return list(page_obj.object_list), {
        "page": page_obj.number,
        "page_size": page_size,
        "total_items": paginator.count,
        "total_pages": paginator.num_pages,
    }


def parse_page(request):
    try:
        page = max(int(request.query_params.get("page", 1)), 1)
        page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 100)
    except (TypeError, ValueError):
        page, page_size = 1, 20
    return page, page_size


def user_full_name(user):
    if not user:
        return ""
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.get_username()


class AdminDashboardView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        data = admin_dashboard_payload(
            date_from=request.query_params.get("date_from"),
            date_to=request.query_params.get("date_to"),
            zone_id=request.query_params.get("zone_id"),
        )
        return Response(envelope(data, "Dashboard loaded"))


class ServiceZoneListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        status_filter = request.query_params.get("status")
        if status_filter:
            status_filter = status_filter.upper()
        metrics = ServiceZoneMetrics(
            city=request.query_params.get("city", "Marawi"),
            include_inactive=parse_bool(request.query_params.get("include_inactive")),
        )
        return Response(envelope(metrics.list_payload(status_filter=status_filter), "Service zones loaded"))


class ServiceZoneDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, zone_id):
        zone = get_object_or_404(ServiceZone, id=zone_id)
        metric = next((item for item in ServiceZoneMetrics(city=zone.city, include_inactive=True).zone_payloads() if item["id"] == str(zone.id)), None)
        merchants = zone_merchants(zone)
        riders = zone_riders(zone)
        store_ids = [store.id for store in merchants]
        orders = Order.objects.select_related("store", "customer").filter(store_id__in=store_ids).order_by("-created_at")[:10]
        rides = [ride for ride in Ride.objects.select_related("rider", "passenger").order_by("-created_at")[:100] if str(zone_for_ride_safe(ride, zone)) == str(zone.id)][:10]

        data = {
            "zone": {
                "id": str(zone.id),
                "name": zone.name,
                "slug": zone.slug,
                "city": zone.city,
                "province": zone.province,
                "center_latitude": str(zone.center_latitude),
                "center_longitude": str(zone.center_longitude),
                "barangay_names": zone.barangay_names,
                "boundary": zone.boundary or None,
                "is_active": zone.is_active,
            },
            "metrics": metric,
            "recent_orders": [
                {
                    "id": str(order.id),
                    "store_name": order.store.name,
                    "status": order.status,
                    "total_amount": float(order.total_amount),
                    "created_at": order.created_at,
                }
                for order in orders
            ],
            "active_transport_bookings": [
                {
                    "id": str(ride.id),
                    "status": ride.status,
                    "requested_vehicle_type": ride.requested_vehicle_type,
                    "estimated_fare": float(ride.estimated_fare),
                    "created_at": ride.created_at,
                }
                for ride in rides
                if ride.status in ACTIVE_RIDE_STATUSES
            ],
            "active_riders": [rider_payload(rider) for rider in riders if rider.is_online],
            "busy_merchants": merchant_payloads(merchants, active_only=True)[:10],
        }
        return Response(envelope(data, "Service zone loaded"))


def zone_for_ride_safe(ride, zone):
    from .services import zone_for_ride

    matched = zone_for_ride(ride, [zone])
    return matched.id if matched else None


class ServiceZoneMerchantsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, zone_id):
        zone = get_object_or_404(ServiceZone, id=zone_id)
        page, page_size = parse_page(request)
        items, pagination = pagination_payload(merchant_payloads(zone_merchants(zone)), page, page_size)
        return Response(envelope({"items": items, "pagination": pagination}, "Zone merchants loaded"))


class ServiceZoneRidersView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, zone_id):
        zone = get_object_or_404(ServiceZone, id=zone_id)
        page, page_size = parse_page(request)
        items, pagination = pagination_payload([rider_payload(rider) for rider in zone_riders(zone)], page, page_size)
        return Response(envelope({"items": items, "pagination": pagination}, "Zone riders loaded"))


class ServiceZoneActivityView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, zone_id):
        zone = get_object_or_404(ServiceZone, id=zone_id)
        merchants = zone_merchants(zone)
        store_ids = [store.id for store in merchants]
        events = []
        for order in Order.objects.select_related("store").filter(store_id__in=store_ids).order_by("-created_at")[:10]:
            events.append(
                {
                    "id": f"order_{order.id}",
                    "type": "order_status",
                    "actor_type": "system",
                    "actor_name": order.store.name,
                    "description": f"Order {str(order.id)[:8]} is {order.status}.",
                    "created_at": order.updated_at,
                }
            )
        events.sort(key=lambda event: event["created_at"], reverse=True)
        return Response(envelope({"events": events[:20]}, "Zone activity loaded"))


class AdminMerchantListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        stores = list(Store.objects.select_related("owner").all().order_by("-created_at"))
        status_filter = request.query_params.get("status")
        search = str(request.query_params.get("search", "")).strip().lower()
        zone_id = request.query_params.get("zone_id")

        if status_filter == "active":
            stores = [store for store in stores if store.is_active]
        elif status_filter in {"paused", "suspended"}:
            stores = [store for store in stores if not store.is_active]
        if search:
            stores = [store for store in stores if search in store.name.lower() or search in user_full_name(store.owner).lower() or search in store.company_email.lower()]
        if zone_id:
            zone = get_object_or_404(ServiceZone, id=zone_id)
            stores = [store for store in stores if zone_for_store(store, [zone]) == zone]

        page, page_size = parse_page(request)
        items, pagination = pagination_payload(merchant_payloads(stores), page, page_size)
        return Response(envelope({"items": items, "pagination": pagination}, "Merchants loaded"))


class AdminMerchantActionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, store_id):
        store = get_object_or_404(Store.objects.select_related("owner"), id=store_id)
        serializer = AdminMerchantActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")

        if action == "PAUSE_ACCOUNT":
            if Order.objects.filter(store=store, status__in=ACTIVE_ORDER_STATUSES).exists():
                return Response(
                    {
                        "detail": (
                            "This merchant still has active orders. Stop new orders "
                            "and complete the live queue before pausing the account."
                        )
                    },
                    status=409,
                )
            store.is_active = False
            store.manual_override = StoreManualOverride.PAUSED_ORDERS
            store.manual_override_reason = reason
        elif action == "REACTIVATE_ACCOUNT":
            store.is_active = True
            store.manual_override = None
            store.manual_override_reason = ""
        elif action == "STOP_ORDERS":
            store.manual_override = StoreManualOverride.CLOSED_TEMPORARILY
            store.manual_override_reason = reason
        else:
            store.manual_override = None
            store.manual_override_reason = ""

        store.save(
            update_fields=[
                "is_active",
                "manual_override",
                "manual_override_reason",
                "updated_at",
            ]
        )
        return Response(envelope(merchant_payloads([store])[0], "Merchant updated"))


class AdminRiderListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        riders = list(RiderProfile.objects.select_related("user").all().order_by("user__first_name", "user__last_name"))
        status_filter = request.query_params.get("status")
        vehicle_type = request.query_params.get("vehicle_type")
        search = str(request.query_params.get("search", "")).strip().lower()
        zone_id = request.query_params.get("zone_id")

        if status_filter == "suspended":
            riders = [rider for rider in riders if not rider.user.is_active]
        elif status_filter == "online":
            riders = [rider for rider in riders if rider.user.is_active and rider.is_online and rider.is_available]
        elif status_filter == "busy":
            riders = [rider for rider in riders if rider.user.is_active and rider.is_online and not rider.is_available]
        elif status_filter == "offline":
            riders = [rider for rider in riders if rider.user.is_active and not rider.is_online]
        if vehicle_type:
            riders = [rider for rider in riders if rider.vehicle_type.lower() == vehicle_type.lower()]
        if search:
            riders = [rider for rider in riders if search in user_full_name(rider.user).lower() or search in rider.user.email.lower()]
        if zone_id:
            zone = get_object_or_404(ServiceZone, id=zone_id)
            riders = [rider for rider in riders if zone_for_rider(rider, [zone]) == zone]

        page, page_size = parse_page(request)
        items, pagination = pagination_payload([rider_payload(rider) for rider in riders], page, page_size)
        return Response(envelope({"items": items, "pagination": pagination}, "Riders loaded"))


class AdminRiderActionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, rider_id):
        rider = get_object_or_404(RiderProfile.objects.select_related("user"), id=rider_id)
        serializer = AdminRiderActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]

        if action == "SUSPEND_ACCOUNT":
            has_active_delivery = Order.objects.filter(
                rider=rider.user,
                status__in=ACTIVE_ORDER_STATUSES,
            ).exists()
            has_active_trip = Ride.objects.filter(
                rider=rider,
                status__in=ACTIVE_RIDE_STATUSES,
            ).exists()
            if has_active_delivery or has_active_trip:
                return Response(
                    {
                        "detail": (
                            "This rider still has an active assignment. Complete or "
                            "reassign it before suspending the account."
                        )
                    },
                    status=409,
                )
            rider.user.is_active = False
            rider.user.save(update_fields=["is_active"])
            rider.is_online = False
            rider.is_available = False
            rider.save(update_fields=["is_online", "is_available"])
        else:
            rider.user.is_active = True
            rider.user.save(update_fields=["is_active"])
            rider.is_online = False
            rider.is_available = True
            rider.save(update_fields=["is_online", "is_available"])

        return Response(envelope(rider_payload(rider), "Rider updated"))


class AdminFinanceOverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response(
            envelope(
                finance_overview(
                    date_from=request.query_params.get("date_from"),
                    date_to=request.query_params.get("date_to"),
                ),
                "Finance overview loaded",
            )
        )


class AdminMarketingOverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response(envelope(marketing_overview(), "Marketing overview loaded"))


class AdminAlertListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        alerts = AdminAlert.objects.all()
        severity = request.query_params.get("severity")
        is_resolved = request.query_params.get("is_resolved")
        if severity:
            alerts = alerts.filter(severity=severity)
        if is_resolved is not None:
            alerts = alerts.filter(is_resolved=parse_bool(is_resolved))
        page, page_size = parse_page(request)
        items, pagination = pagination_payload([alert_payload(alert) for alert in alerts], page, page_size)
        return Response(envelope({"items": items, "pagination": pagination}, "System alerts loaded"))


class AdminAlertResolveView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def patch(self, request, alert_id):
        alert = get_object_or_404(AdminAlert, id=alert_id)
        alert.mark_resolved(request.user)
        return Response(envelope(alert_payload(alert), "System alert resolved"))


def merchant_payloads(stores, active_only=False):
    payloads = []
    zones = list(ServiceZone.objects.filter(is_active=True))
    for store in stores:
        active_orders = Order.objects.filter(store=store, status__in=ACTIVE_ORDER_STATUSES).count()
        if active_only and active_orders == 0:
            continue
        zone = zone_for_store(store, zones)
        delivered_orders = Order.objects.filter(store=store, status=OrderStatus.DELIVERED)
        payloads.append(
            {
                "id": str(store.id),
                "store_name": store.name,
                "branch_name": store.branch_name,
                "owner_name": user_full_name(store.owner),
                "email": store.company_email or store.owner.email,
                "contact_number": store.contact_number,
                "status": "active" if store.is_active else "paused",
                "zone": {"id": str(zone.id), "name": zone.name} if zone else None,
                "is_open": store.is_open,
                "manual_override": store.manual_override,
                "status_reason": store.manual_override_reason,
                "rating": float(store.rating),
                "total_orders": delivered_orders.count(),
                "active_orders": active_orders,
                "gmv_amount": float(delivered_orders.aggregate(total=Sum("total_amount"))["total"] or 0),
                "latitude": str(store.latitude),
                "longitude": str(store.longitude),
                "created_at": store.created_at,
            }
        )
    return payloads


def rider_payload(rider):
    zones = list(ServiceZone.objects.filter(is_active=True))
    zone = zone_for_rider(rider, zones)
    completed_deliveries = Order.objects.filter(rider=rider.user, status=OrderStatus.DELIVERED).count()
    completed_trips = Ride.objects.filter(rider=rider, status=RideStatus.COMPLETED).count()
    if not rider.user.is_active:
        status_value = "suspended"
    elif not rider.is_online:
        status_value = "offline"
    elif not rider.is_available:
        status_value = "busy"
    else:
        status_value = "online"
    return {
        "id": str(rider.id),
        "full_name": user_full_name(rider.user),
        "email": rider.user.email,
        "contact_number": rider.user.phone_number,
        "status": status_value,
        "vehicle_type": rider.vehicle_type.lower(),
        "plate_number": rider.plate_number,
        "zone": {"id": str(zone.id), "name": zone.name} if zone else None,
        "is_available": rider.is_available,
        "completed_deliveries": completed_deliveries,
        "completed_trips": completed_trips,
        "wallet_balance": float(rider.balance),
        "current_latitude": str(rider.current_latitude) if rider.current_latitude is not None else None,
        "current_longitude": str(rider.current_longitude) if rider.current_longitude is not None else None,
        "last_location_update_at": rider.last_location_update,
        "account_is_active": rider.user.is_active,
    }


def alert_payload(alert):
    return {
        "id": str(alert.id),
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "source": alert.source,
        "is_resolved": alert.is_resolved,
        "created_at": alert.created_at,
    }
