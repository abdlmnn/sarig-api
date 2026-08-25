from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.common.money import money, money_payload
from apps.vendors.utils import PH_TZ

from .models import DeliveryMethod, Order, OrderStatus


ACTIVE_STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.ACCEPTED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
    OrderStatus.ON_THE_WAY,
]
PREP_TARGET_MINUTES = 15


def minutes_label(minutes):
    return f"{int(minutes)} min"


def status_label(status, vertical_slug=""):
    if status == OrderStatus.ACCEPTED:
        return {
            "grocery": "Accepted",
            "pharmacy": "Accepted",
            "restaurant": "Accepted",
        }.get(vertical_slug, "Accepted")
    if status == OrderStatus.PREPARING:
        return {
            "grocery": "Picking items",
            "pharmacy": "Verifying order",
            "restaurant": "Preparing",
        }.get(vertical_slug, "Preparing")
    if status == OrderStatus.READY:
        return {
            "grocery": "Packed",
            "pharmacy": "Ready for pickup",
            "restaurant": "Ready",
        }.get(vertical_slug, "Ready")

    return {
        OrderStatus.PENDING: "New",
        OrderStatus.ON_THE_WAY: "On delivery",
        OrderStatus.DELIVERED: "Delivered",
        OrderStatus.CANCELLED: "Cancelled",
    }.get(status, status.replace("_", " ").title())


def activity_status(status):
    return {
        OrderStatus.PENDING: "NEW",
        OrderStatus.ACCEPTED: "ACCEPTED",
        OrderStatus.PREPARING: "PREPARING",
        OrderStatus.READY: "READY",
        OrderStatus.ON_THE_WAY: "ON_DELIVERY",
        OrderStatus.DELIVERED: "DELIVERED",
        OrderStatus.CANCELLED: "CANCELLED",
    }.get(status, status)


def day_bounds(target_date):
    start = datetime.combine(target_date, time.min, tzinfo=PH_TZ)
    end = start + timedelta(days=1)
    return start.astimezone(dt_timezone.utc), end.astimezone(dt_timezone.utc)


def parse_activity_date(request):
    raw_date = request.query_params.get("date")
    if raw_date:
        try:
            return datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    return timezone.now().astimezone(PH_TZ).date()


def settlement_label(next_settlement, target_date):
    if target_date == timezone.now().astimezone(PH_TZ).date():
        return "Tomorrow, 10:00 AM"
    return next_settlement.strftime("%b %d, %I:%M %p").replace(" 0", " ")


def order_items_summary(order):
    items = list(order.items.all())
    if not items:
        return ""

    labels = []
    for item in items[:2]:
        name = item.product.name
        labels.append(f"{item.quantity}x {name}" if item.quantity > 1 else name)
    if len(items) > 2:
        labels.append(f"+{len(items) - 2} more")
    return ", ".join(labels)


def customer_name(order):
    full_name = order.customer.get_full_name()
    return full_name or order.customer.username


def rider_name(order):
    if not order.rider_id:
        return None
    return order.rider.get_full_name() or order.rider.username


def merchant_order_summary(order, now=None):
    now = now or timezone.now()
    vertical_slug = (
        order.store.vertical.slug
        if order.store_id and order.store.vertical_id
        else ""
    )
    age_minutes = max(
        int((now - order.created_at).total_seconds() // 60),
        0,
    )
    eta_minutes = 0
    if order.status in [
        OrderStatus.PENDING,
        OrderStatus.ACCEPTED,
        OrderStatus.PREPARING,
    ]:
        eta_minutes = max(PREP_TARGET_MINUTES - age_minutes, 0)
    elif order.status == OrderStatus.READY:
        eta_minutes = 9
    elif order.status == OrderStatus.ON_THE_WAY and order.estimated_arrival_time:
        eta_minutes = max(
            int((order.estimated_arrival_time - now).total_seconds() // 60),
            0,
        )

    assigned_rider = rider_name(order)
    return {
        "order_id": str(order.id),
        "id": f"SRG-{str(order.id)[:8].upper()}",
        "customer_name": customer_name(order),
        "items_summary": order_items_summary(order),
        "status": activity_status(order.status),
        "status_label": status_label(order.status, vertical_slug),
        "store_vertical_slug": vertical_slug,
        "rider_name": assigned_rider,
        "rider_label": assigned_rider or ("Assigned" if order.rider_id else "Waiting"),
        "eta_minutes": eta_minutes,
        "eta_label": minutes_label(eta_minutes),
        "delivery_method": order.delivery_method,
        "total_amount": str(money(order.total_amount)),
        "created_at": order.created_at.isoformat(),
    }


def delivery_lane(address):
    if not address:
        return "Marawi City"
    return address.split(",")[0].strip()[:80] or "Marawi City"


def build_store_order_activity(request):
    stores = list(request.user.stores.filter(is_active=True).order_by("name"))
    if not stores:
        return None

    store_ids = [store.id for store in stores]
    primary_store = stores[0]
    target_date = parse_activity_date(request)
    today_start, today_end = day_bounds(target_date)
    yesterday_start, yesterday_end = day_bounds(target_date - timedelta(days=1))
    now = timezone.now()

    orders = Order.objects.filter(store_id__in=store_ids)
    today_orders = orders.filter(created_at__gte=today_start, created_at__lt=today_end)
    yesterday_orders = orders.filter(created_at__gte=yesterday_start, created_at__lt=yesterday_end)
    active_orders_qs = (
        today_orders.filter(status__in=ACTIVE_STATUSES)
        .select_related("customer", "rider", "store__vertical")
        .prefetch_related("items__product")
        .order_by("created_at", "id")
    )

    today_count = today_orders.count()
    yesterday_count = yesterday_orders.count()
    change = today_count - yesterday_count

    preparing_qs = orders.filter(status=OrderStatus.PREPARING)
    attention_count = preparing_qs.filter(updated_at__lte=now - timedelta(minutes=PREP_TARGET_MINUTES)).count()
    on_delivery_qs = orders.filter(status=OrderStatus.ON_THE_WAY)
    delivered_delivery_today = today_orders.filter(
        status=OrderStatus.DELIVERED,
        delivery_method=DeliveryMethod.DELIVERY,
        delivered_at__isnull=False,
    )

    delivery_minutes = [
        max(int((order.delivered_at - order.created_at).total_seconds() // 60), 0)
        for order in delivered_delivery_today.only("created_at", "delivered_at")
    ]
    average_delivery_minutes = round(sum(delivery_minutes) / len(delivery_minutes)) if delivery_minutes else 0

    gross_sales = money(today_orders.exclude(status=OrderStatus.CANCELLED).aggregate(total=Sum("total_amount"))["total"])
    commission_rate = money(primary_store.commission_rate) / Decimal("100.00")
    fees = money(gross_sales * commission_rate)
    net_sales = money(gross_sales - fees)

    pipeline_counts = Counter(orders.filter(status__in=ACTIVE_STATUSES).values_list("status", flat=True))
    incoming_count = today_orders.exclude(status=OrderStatus.CANCELLED).count()
    accepted_count = today_orders.filter(
        status__in=[
            OrderStatus.ACCEPTED,
            OrderStatus.PREPARING,
            OrderStatus.READY,
            OrderStatus.ON_THE_WAY,
            OrderStatus.DELIVERED,
        ]
    ).count()
    acceptance_rate = round((accepted_count / incoming_count) * 100) if incoming_count else 100

    prep_durations = [
        max(int((order.updated_at - order.created_at).total_seconds() // 60), 0)
        for order in today_orders.filter(
            status__in=[OrderStatus.READY, OrderStatus.ON_THE_WAY, OrderStatus.DELIVERED]
        ).only("created_at", "updated_at")
    ]
    average_prep_time = round(sum(prep_durations) / len(prep_durations)) if prep_durations else 0
    pickup_delay = 0

    active_payload = []
    for order in active_orders_qs[:10]:
        active_payload.append(merchant_order_summary(order, now))

    alerts = []
    if attention_count:
        alerts.append(
            {
                "id": "order-delay",
                "type": "ORDER_DELAY",
                "severity": "WARNING",
                "message": f"{attention_count} preparing orders are close to their promised pickup time.",
            }
        )
    if pickup_delay > 5:
        alerts.append(
            {
                "id": "pickup-delay",
                "type": "PICKUP_DELAY",
                "severity": "WARNING",
                "message": f"Average pickup delay is {pickup_delay} minutes.",
            }
        )

    lane_rows = today_orders.filter(delivery_method=DeliveryMethod.DELIVERY).values(
        "delivery_address_text"
    ).annotate(orders=Count("id"))
    lane_counts = defaultdict(int)
    for row in lane_rows:
        lane_counts[delivery_lane(row["delivery_address_text"])] += row["orders"]

    delivery_lanes = []
    for area, count in sorted(lane_counts.items(), key=lambda item: item[1], reverse=True)[:5]:
        average_time = average_delivery_minutes or 0
        load = "WATCH" if average_time >= 30 else "HIGH" if count >= 10 else "STABLE"
        delivery_lanes.append(
            {
                "area": area,
                "orders": count,
                "average_time_minutes": average_time,
                "average_time_label": minutes_label(average_time),
                "load": load,
                "load_label": load.title(),
            }
        )

    next_settlement = datetime.combine(target_date + timedelta(days=1), time(hour=10), tzinfo=PH_TZ)

    return {
        "stats": {
            "orders_today": {
                "value": today_count,
                "change": change,
                "change_label": f"{change:+d} from yesterday",
            },
            "preparing_now": {
                "value": preparing_qs.count(),
                "attention_count": attention_count,
                "note": f"{attention_count} need attention",
            },
            "on_delivery": {
                "value": on_delivery_qs.count(),
                "average_delivery_minutes": average_delivery_minutes,
                "note": f"Average {average_delivery_minutes} min",
            },
            "net_sales": {
                **money_payload(net_sales),
                "note": "After service fees",
            },
        },
        "order_pipeline": {
            "new": pipeline_counts[OrderStatus.PENDING],
            "accepted": pipeline_counts[OrderStatus.ACCEPTED],
            "preparing": pipeline_counts[OrderStatus.PREPARING],
            "ready": pipeline_counts[OrderStatus.READY],
            "assigned": pipeline_counts[OrderStatus.ON_THE_WAY],
        },
        "active_orders": active_payload,
        "service_health": {
            "acceptance_rate": {
                "value": acceptance_rate,
                "formatted": f"{acceptance_rate}%",
                "status": "STRONG" if acceptance_rate >= 95 else "WATCH",
                "label": "Strong" if acceptance_rate >= 95 else "Watch",
            },
            "average_prep_time": {
                "value_minutes": average_prep_time,
                "formatted": f"{average_prep_time}m",
                "target_minutes": PREP_TARGET_MINUTES,
                "note": f"Target {PREP_TARGET_MINUTES}m",
            },
            "pickup_delay": {
                "value_minutes": pickup_delay,
                "formatted": f"{pickup_delay}m",
                "status": "STABLE" if pickup_delay <= 5 else "WATCH",
                "label": "Stable" if pickup_delay <= 5 else "Watch",
            },
        },
        "alerts": alerts,
        "settlement": {
            "gross_sales": money_payload(gross_sales),
            "fees": money_payload(fees),
            "expected_payout": money_payload(net_sales),
            "next_settlement_window": {
                "datetime": next_settlement.isoformat(),
                "label": settlement_label(next_settlement, target_date),
            },
        },
        "delivery_lanes": delivery_lanes,
    }


def merchant_order_summary(order, now=None):
    now = now or timezone.now()
    vertical_slug = order.store.vertical.slug if order.store_id and order.store.vertical_id else ""
    age_minutes = max(int((now - order.created_at).total_seconds() // 60), 0)
    eta_minutes = max(PREP_TARGET_MINUTES - age_minutes, 0) if order.status in [
        OrderStatus.PENDING,
        OrderStatus.ACCEPTED,
        OrderStatus.PREPARING,
    ] else 0
    if order.status == OrderStatus.READY:
        eta_minutes = 9
    elif order.status == OrderStatus.ON_THE_WAY and order.estimated_arrival_time:
        eta_minutes = max(int((order.estimated_arrival_time - now).total_seconds() // 60), 0)

    return {
        "order_id": str(order.id),
        "id": f"SRG-{str(order.id)[:8].upper()}",
        "customer_name": customer_name(order),
        "items_summary": order_items_summary(order),
        "status": activity_status(order.status),
        "status_label": status_label(order.status, vertical_slug),
        "store_vertical_slug": vertical_slug,
        "rider_name": rider_name(order),
        "rider_label": rider_name(order) or ("Assigned" if order.rider_id else "Waiting"),
        "eta_minutes": eta_minutes,
        "eta_label": minutes_label(eta_minutes),
        "created_at": order.created_at.isoformat(),
        "total_amount": str(money(order.total_amount)),
        "delivery_method": order.delivery_method,
    }


def order_tracking_payload(order):
    rider_profile = (
        getattr(order.rider, "rider_profile", None)
        if order.status == OrderStatus.ON_THE_WAY
        else None
    )
    rider_latitude = getattr(rider_profile, "current_latitude", None)
    rider_longitude = getattr(rider_profile, "current_longitude", None)
    rider_updated_at = getattr(rider_profile, "last_location_update", None)

    return {
        "store": {
            "latitude": str(order.store.latitude),
            "longitude": str(order.store.longitude),
        },
        "customer": {
            "latitude": str(order.delivery_latitude),
            "longitude": str(order.delivery_longitude),
        },
        "rider": (
            {
                "latitude": str(rider_latitude),
                "longitude": str(rider_longitude),
                "last_updated_at": rider_updated_at.isoformat()
                if rider_updated_at
                else None,
            }
            if rider_latitude is not None and rider_longitude is not None
            else None
        ),
    }
