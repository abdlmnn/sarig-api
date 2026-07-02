from datetime import timedelta
from decimal import Decimal
import logging

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.onboarding.models import ApplicationStatus, MerchantApplication
from apps.onboarding.services import ApplicationService
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.riders.services import RiderDispatcherService
from apps.users.geo import get_lat_lng
from apps.users.permissions import IsMerchant
from .dashboard import build_merchant_dashboard_overview, store_availability_payload, PH_TZ
from .models import Store, BusinessVertical, StoreManualOverride
from .serializers import StoreSerializer, BusinessVerticalSerializer, StoreStatusUpdateSerializer
from .permissions import IsMerchantOrAdmin

logger = logging.getLogger(__name__)

ACTIVE_ORDER_STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.ACCEPTED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
    OrderStatus.ON_THE_WAY,
]


def money_payload(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"))
    return {
        "value": str(amount),
        "currency": "PHP",
        "formatted": f"₱{amount:,.0f}",
    }


def short_name(user):
    full_name = user.get_full_name().strip()
    if full_name:
        parts = full_name.split()
        if len(parts) > 1:
            return f"{parts[0]} {parts[-1][0]}."
        return parts[0]
    return user.username


def order_id_label(order):
    return f"SRG-{str(order.id).split('-')[0].upper()}"


def status_label(value):
    return value.replace("_", " ").title()


def eta_payload(order, fallback_minutes=0):
    if order.estimated_arrival_time:
        minutes = max(
            int((order.estimated_arrival_time - timezone.now()).total_seconds() // 60),
            0,
        )
    else:
        minutes = fallback_minutes
    return minutes, f"{minutes} min"


def items_summary(order):
    items = list(order.items.select_related("product").all()[:3])
    if not items:
        return "Items unavailable"

    labels = []
    for item in items[:2]:
        name = item.product.name
        labels.append(f"{item.quantity}x {name}" if item.quantity > 1 else name)

    if len(items) > 2:
        labels.append(f"+{len(items) - 2} more")

    return ", ".join(labels)


def next_settlement_window():
    target = timezone.localtime(timezone.now()) + timedelta(days=1)
    target = target.replace(hour=10, minute=0, second=0, microsecond=0)
    return {
        "datetime": target.isoformat(),
        "label": "Tomorrow, 10:00 AM",
    }


def delivery_lane_payload(orders):
    lanes = {}
    for order in orders:
        area = order.delivery_address_text.split(",")[0].strip() or "Marawi City"
        lanes.setdefault(area, 0)
        lanes[area] += 1

    return [
        {
            "area": area,
            "orders": count,
            "average_time_minutes": 0,
            "average_time_label": "0 min",
            "load": "STABLE",
            "load_label": "Stable",
        }
        for area, count in sorted(lanes.items(), key=lambda item: item[1], reverse=True)[:5]
    ]


def merchant_dashboard_payload(store):
    now = timezone.localtime(timezone.now())
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    orders = (
        Order.objects.filter(store=store)
        .select_related("customer", "rider")
        .prefetch_related("items__product")
    )
    today_orders = orders.filter(created_at__gte=today_start)
    yesterday_orders = orders.filter(created_at__gte=yesterday_start, created_at__lt=today_start)
    active_orders = today_orders.filter(status__in=ACTIVE_ORDER_STATUSES).order_by("-created_at")[:10]
    delivered_today = today_orders.filter(status=OrderStatus.DELIVERED)

    gross_sales = delivered_today.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    fees = delivered_today.aggregate(total=Sum("system_fee"))["total"] or Decimal("0.00")
    expected_payout = gross_sales - fees
    preparing_count = today_orders.filter(status=OrderStatus.PREPARING).count()
    on_delivery_count = today_orders.filter(status=OrderStatus.ON_THE_WAY).count()
    accepted_count = today_orders.exclude(status=OrderStatus.PENDING).count()
    total_today = today_orders.count()
    acceptance_rate = round((accepted_count / total_today) * 100) if total_today else 100
    acceptance_status = "STRONG" if acceptance_rate >= 95 else "WATCH"

    active_order_rows = []
    for order in active_orders:
        eta_minutes, eta_label = eta_payload(order, 12 if order.status != OrderStatus.ON_THE_WAY else 35)
        active_order_rows.append(
            {
                "id": order_id_label(order),
                "customer_name": short_name(order.customer),
                "items_summary": items_summary(order),
                "status": order.status,
                "status_label": status_label(order.status),
                "rider_name": short_name(order.rider) if order.rider else None,
                "rider_label": "Assigned" if order.rider else "Waiting",
                "eta_minutes": eta_minutes,
                "eta_label": eta_label,
            }
        )

    availability = store_availability_payload(store)
    return {
        "merchant": {
            "id": str(store.id),
            "business_name": store.name,
            **availability,
            "next_status_change": None,
            "service_modes": ["DELIVERY", "PICKUP"],
            "last_updated": store.updated_at.isoformat(),
        },
        "stats": {
            "orders_today": {
                "value": total_today,
                "change": total_today - yesterday_orders.count(),
                "change_label": f"{total_today - yesterday_orders.count():+d} from yesterday",
            },
            "preparing_now": {
                "value": preparing_count,
                "attention_count": preparing_count,
                "note": f"{preparing_count} need attention",
            },
            "on_delivery": {
                "value": on_delivery_count,
                "average_delivery_minutes": 0,
                "note": "Average 0 min",
            },
            "net_sales": {
                **money_payload(expected_payout),
                "note": "After service fees",
            },
        },
        "order_pipeline": {
            "new": today_orders.filter(status=OrderStatus.PENDING).count(),
            "accepted": today_orders.filter(status=OrderStatus.ACCEPTED).count(),
            "preparing": preparing_count,
            "ready": today_orders.filter(status=OrderStatus.READY).count(),
            "assigned": today_orders.filter(status=OrderStatus.ON_THE_WAY).count(),
        },
        "active_orders": active_order_rows,
        "service_health": {
            "acceptance_rate": {
                "value": acceptance_rate,
                "formatted": f"{acceptance_rate}%",
                "status": acceptance_status,
                "label": "Strong" if acceptance_status == "STRONG" else "Watch",
            },
            "average_prep_time": {
                "value_minutes": 0,
                "formatted": "0m",
                "target_minutes": 15,
                "note": "Target 15m",
            },
            "pickup_delay": {
                "value_minutes": 0,
                "formatted": "0m",
                "status": "STABLE",
                "label": "Stable",
            },
        },
        "alerts": [
            {
                "id": "document-status",
                "type": "DOCUMENT_STATUS",
                "severity": "INFO",
                "message": "Store documents are verified. No onboarding action required.",
            }
        ],
        "settlement": {
            "gross_sales": money_payload(gross_sales),
            "fees": money_payload(fees),
            "expected_payout": money_payload(expected_payout),
            "next_settlement_window": next_settlement_window(),
        },
        "delivery_lanes": delivery_lane_payload(today_orders.filter(status__in=ACTIVE_ORDER_STATUSES)),
    }


def store_availability_payload(store):
    if store.manual_override == StoreManualOverride.OPEN_NOW:
        return {
            "status": "OPEN",
            "status_label": "Open",
            "status_reason": store.manual_override_reason or "Accepting orders now",
            "manual_override": store.manual_override,
        }

    if store.manual_override == StoreManualOverride.PAUSED_ORDERS:
        return {
            "status": "PAUSED",
            "status_label": "Paused",
            "status_reason": store.manual_override_reason or "Orders paused",
            "manual_override": store.manual_override,
        }

    if store.manual_override in (
        StoreManualOverride.CLOSED_MANUALLY,
        StoreManualOverride.CLOSED_TEMPORARILY,
    ):
        return {
            "status": "CLOSED",
            "status_label": "Closed",
            "status_reason": store.manual_override_reason or "Not accepting orders",
            "manual_override": store.manual_override,
        }

    return {
        "status": "OPEN" if store.is_open else "CLOSED",
        "status_label": "Open" if store.is_open else "Closed",
        "status_reason": "Following store hours",
        "manual_override": None,
    }


def get_or_create_merchant_store(user):
    store = Store.objects.filter(owner=user, is_active=True).first()
    if store:
        return store

    application = (
        MerchantApplication.objects.filter(
            applicant=user,
            status=ApplicationStatus.APPROVED,
        )
        .order_by("-updated_at")
        .first()
    )
    if not application:
        return None

    return ApplicationService.create_store_for_merchant(application)


class BusinessVerticalViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BusinessVerticalSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return BusinessVertical.objects.filter(
            is_active=True,
            slug__in=[
                "restaurant",
                "pharmacy",
                "grocery",
                "market",
                "convenience-store",
                "general-store",
                "bakery",
            ],
        )


class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer
    permission_classes = [IsMerchantOrAdmin]

    def get_queryset(self):
        queryset = Store.objects.select_related("vertical", "owner")

        # Own stores only (Filter merchant)
        user = self.request.user

        # only own stores unless admin
        if not user.is_staff:
            queryset = queryset.filter(owner=user)

        lat = self.request.query_params.get("lat")
        lng = self.request.query_params.get("lng")
        radius = self.request.query_params.get("radius")

        # Optional geo filter for staff/ops listing, dual-mode safe.
        if lat and lng and radius:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                radius_f = float(radius)
            except (TypeError, ValueError):
                return queryset

            if getattr(settings, "USE_POSTGIS", False):
                try:
                    user_location = Point(lng_f, lat_f, srid=4326)
                    return (
                        queryset.filter(location_point__isnull=False)
                        .filter(location_point__distance_lte=(user_location, D(km=radius_f)))
                        .annotate(distance=Distance("location_point", user_location))
                        .order_by("distance")
                    )
                except (ValueError, TypeError) as exc:
                    logger.warning("StoreViewSet PostGIS geo filter fallback due to invalid input: %s", exc)
                except Exception as exc:
                    logger.warning("StoreViewSet PostGIS geo filter fallback due to runtime error: %s", exc)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user

        # ensure only merchants can create stores
        if not user.is_staff and not user.roles.filter(name__iexact="Merchant").exists():
            raise PermissionDenied("Only merchants can create stores.")

        serializer.save(owner=user)


class MerchantStoreStatusView(APIView):
    permission_classes = [IsMerchant]

    def patch(self, request):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        serializer = StoreStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        store.manual_override = serializer.validated_data.get("manual_override")
        store.manual_override_reason = serializer.validated_data.get("reason", "")
        store.save(update_fields=["manual_override", "manual_override_reason", "updated_at"])

        return Response({"store_id": str(store.id), **store_availability_payload(store)})


class MerchantDashboardOverviewView(APIView):
    permission_classes = [IsMerchant]

    def get(self, request):
        store = get_or_create_merchant_store(request.user)
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        return Response(merchant_dashboard_payload(store))


class MerchantAnalyticsView(APIView):
    permission_classes = [IsMerchantOrAdmin]

    def get(self, request, store_id):
        store = get_object_or_404(Store, id=store_id)
        
        # Security Check
        if not request.user.is_staff and store.owner != request.user:
            raise PermissionDenied("You do not own this store.")

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=7)

        # 1. Financial Overview (Only Delivered orders count as Revenue)
        delivered_orders = Order.objects.filter(store=store, status=OrderStatus.DELIVERED)
        
        total_revenue = delivered_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_orders = delivered_orders.count()
        
        today_revenue = delivered_orders.filter(created_at__gte=today_start).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        today_orders = delivered_orders.filter(created_at__gte=today_start).count()

        # 2. Top Selling Products
        top_products = OrderItem.objects.filter(
            order__store=store, 
            order__status=OrderStatus.DELIVERED
        ).values(
            'product__name'
        ).annotate(
            total_sold=Sum('quantity')
        ).order_by('-total_sold')[:5]

        # 3. 7-Day Sales Trend
        sales_trend = delivered_orders.filter(
            created_at__gte=seven_days_ago
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            daily_revenue=Sum('total_amount'),
            daily_orders=Count('id')
        ).order_by('date')

        return Response({
            "overview": {
                "total_revenue": float(total_revenue),
                "total_orders": total_orders,
                "today_revenue": float(today_revenue),
                "today_orders": today_orders,
            },
            "top_products": top_products,
            "sales_trend": list(sales_trend)
        })


class NearbyStoresView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "nearby_stores"

    def get(self, request):
        lat = request.query_params.get("lat")
        lng = request.query_params.get("lng")
        radius = request.query_params.get("radius")
        
        if not lat or not lng:
            return Response({"error": "Latitude and Longitude are required."}, status=400)
        try:
            lat_f = float(lat)
            lng_f = float(lng)
            radius_f = float(radius) if radius is not None else None
        except (TypeError, ValueError):
            return Response({"error": "Invalid latitude/longitude/radius values."}, status=400)
        if not (-90 <= lat_f <= 90) or not (-180 <= lng_f <= 180):
            return Response({"error": "Latitude/Longitude out of valid range."}, status=400)
        if radius_f is not None and radius_f <= 0:
            return Response({"error": "Radius must be greater than 0."}, status=400)

        stores = (
            Store.objects.filter(is_active=True)
            .select_related("vertical")
            .annotate(avg_store_rating=Avg("reviews__store_rating"))
        )

        results = []

        # Prefer PostGIS query path, but keep Haversine fallback for dual-mode rollout.
        if getattr(settings, "USE_POSTGIS", False):
            try:
                user_point = Point(lng_f, lat_f, srid=4326)
                stores = stores.filter(location_point__isnull=False)
                if radius_f is not None:
                    stores = stores.filter(location_point__distance_lte=(user_point, D(km=radius_f)))
                stores = stores.annotate(distance=Distance("location_point", user_point)).order_by("distance")
            except (ValueError, TypeError) as exc:
                logger.warning("NearbyStoresView PostGIS fallback due to invalid geo input: %s", exc)
            except Exception as exc:
                logger.warning("NearbyStoresView PostGIS fallback due to runtime error: %s", exc)

        for store in stores:
            store_lat, store_lng = get_lat_lng(store, "latitude", "longitude")
            if hasattr(store, "distance") and store.distance is not None:
                distance = float(
                    store.distance.km if hasattr(store.distance, "km") else store.distance
                )
            else:
                distance = RiderDispatcherService.haversine(
                    lng_f,
                    lat_f,
                    float(store_lng),
                    float(store_lat),
                )
                if radius_f is not None and distance > radius_f:
                    continue

            avg_rating = store.avg_store_rating or 0

            results.append({
                "id": str(store.id),
                "name": store.name,
                "vertical": store.vertical.name if store.vertical else None,
                "address": store.street_address,
                "distance_km": round(distance, 2),
                "rating": round(avg_rating, 1),
                "is_open": store.is_open,
                "logo": store.image.url if store.image else None,
            })

        # Ensure stable ordering when fallback path is used.
        results.sort(key=lambda x: x["distance_km"])

        return Response(results)


class MerchantDashboardOverviewView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "search"

    def get(self, request):
        payload = build_merchant_dashboard_overview(request)
        if payload is None:
            return Response({"detail": "No active store found for this merchant."}, status=404)
        return Response(payload)


class MerchantStoreStatusView(APIView):
    permission_classes = [IsMerchant]
    throttle_scope = "search"

    def patch(self, request):
        store = request.user.stores.filter(is_active=True).order_by("name").first()
        if not store:
            return Response({"detail": "No active store found for this merchant."}, status=404)

        serializer = StoreStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        store.manual_override = serializer.validated_data.get("manual_override")
        store.manual_override_reason = serializer.validated_data.get("reason", "")
        store.save(update_fields=["manual_override", "manual_override_reason", "updated_at"])

        availability = store_availability_payload(store, timezone.now().astimezone(PH_TZ))
        return Response(
            {
                "store_id": str(store.id),
                **availability,
            }
        )
