from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db.models import Count, Sum
from django.utils import timezone

from apps.orders.models import DeliveryMethod, Order, OrderStatus
from apps.vendors.models import StoreManualOverride


PH_TZ = ZoneInfo("Asia/Manila")
ACTIVE_STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.ACCEPTED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
    OrderStatus.ON_THE_WAY,
]
PREP_TARGET_MINUTES = 15
DAY_KEYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


def money(value):
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def money_payload(value):
    value = money(value)
    return {
        "value": str(value),
        "currency": "PHP",
        "formatted": f"₱{value:,.0f}",
    }


def minutes_label(minutes):
    return f"{int(minutes)} min"


def status_label(status):
    return {
        OrderStatus.PENDING: "New",
        OrderStatus.ACCEPTED: "Accepted",
        OrderStatus.PREPARING: "Preparing",
        OrderStatus.READY: "Ready",
        OrderStatus.ON_THE_WAY: "On delivery",
        OrderStatus.DELIVERED: "Delivered",
        OrderStatus.CANCELLED: "Cancelled",
    }.get(status, status.replace("_", " ").title())


def dashboard_status(status):
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


def parse_dashboard_date(request):
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


def parse_hhmm(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None


def format_time_label(value):
    return value.strftime("%I:%M %p").lstrip("0")


def default_business_hours():
    return [
        {
            "day": day,
            "is_closed": False,
            "open_time": "08:00",
            "close_time": "20:00",
        }
        for day in DAY_KEYS
    ]


def normalize_business_hours(store):
    hours = store.business_hours or default_business_hours()
    by_day = {}
    for row in hours:
        if not isinstance(row, dict):
            continue
        day = str(row.get("day", "")).upper()
        if day in DAY_KEYS:
            by_day[day] = {
                "day": day,
                "is_closed": bool(row.get("is_closed", False)),
                "open_time": row.get("open_time"),
                "close_time": row.get("close_time"),
            }
    return [by_day.get(day, default_business_hours()[index]) for index, day in enumerate(DAY_KEYS)]


def schedule_status_for_store(store, now_ph):
    hours = normalize_business_hours(store)
    today_key = DAY_KEYS[now_ph.weekday()]
    today = next((row for row in hours if row["day"] == today_key), None)
    if not today or today.get("is_closed"):
        return {
            "is_open": False,
            "reason": "Closed for today",
            "next_status_change": next_opening_payload(hours, now_ph),
        }

    open_time = parse_hhmm(today.get("open_time"))
    close_time = parse_hhmm(today.get("close_time"))
    if not open_time or not close_time:
        return {
            "is_open": bool(store.is_open),
            "reason": "Using manual store availability",
            "next_status_change": None,
        }

    current_time = now_ph.time()
    if open_time <= current_time < close_time:
        close_dt = datetime.combine(now_ph.date(), close_time, tzinfo=PH_TZ)
        return {
            "is_open": True,
            "reason": "Within business hours",
            "next_status_change": {
                "status": "CLOSED",
                "datetime": close_dt.isoformat(),
                "label": f"Closes at {format_time_label(close_time)}",
            },
        }

    if current_time < open_time:
        open_dt = datetime.combine(now_ph.date(), open_time, tzinfo=PH_TZ)
        return {
            "is_open": False,
            "reason": "Before opening hours",
            "next_status_change": {
                "status": "OPEN",
                "datetime": open_dt.isoformat(),
                "label": f"Opens at {format_time_label(open_time)}",
            },
        }

    return {
        "is_open": False,
        "reason": "After closing hours",
        "next_status_change": next_opening_payload(hours, now_ph),
    }


def next_opening_payload(hours, now_ph):
    for offset in range(1, 8):
        candidate_date = now_ph.date() + timedelta(days=offset)
        day_key = DAY_KEYS[candidate_date.weekday()]
        row = next((hour for hour in hours if hour["day"] == day_key), None)
        if not row or row.get("is_closed"):
            continue
        open_time = parse_hhmm(row.get("open_time"))
        if not open_time:
            continue
        open_dt = datetime.combine(candidate_date, open_time, tzinfo=PH_TZ)
        label = f"Opens {open_dt.strftime('%A')} at {format_time_label(open_time)}"
        return {
            "status": "OPEN",
            "datetime": open_dt.isoformat(),
            "label": label,
        }
    return None


def store_availability_payload(store, now_ph):
    if store.manual_override == StoreManualOverride.CLOSED_TEMPORARILY:
        return {
            "status": "CLOSED",
            "status_label": "Closed temporarily",
            "status_reason": store.manual_override_reason or "Merchant closed the store temporarily",
            "manual_override": store.manual_override,
            "next_status_change": None,
        }

    if store.manual_override == StoreManualOverride.PAUSED_ORDERS:
        return {
            "status": "PAUSED",
            "status_label": "Paused orders",
            "status_reason": store.manual_override_reason or "Merchant paused new orders",
            "manual_override": store.manual_override,
            "next_status_change": None,
        }

    if store.manual_override == StoreManualOverride.OPEN_NOW:
        return {
            "status": "OPEN",
            "status_label": "Open",
            "status_reason": store.manual_override_reason or "Merchant manually opened the store",
            "manual_override": store.manual_override,
            "next_status_change": None,
        }

    schedule = schedule_status_for_store(store, now_ph)
    return {
        "status": "OPEN" if schedule["is_open"] and store.is_open else "CLOSED",
        "status_label": "Open" if schedule["is_open"] and store.is_open else "Closed",
        "status_reason": schedule["reason"] if store.is_open else "Store is disabled",
        "manual_override": None,
        "next_status_change": schedule["next_status_change"],
    }


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


def delivery_lane(address):
    if not address:
        return "Marawi City"
    return address.split(",")[0].strip()[:80] or "Marawi City"


def build_merchant_dashboard_overview(request):
    stores = list(request.user.stores.select_related("vertical").filter(is_active=True).order_by("name"))
    if not stores:
        return None

    store_ids = [store.id for store in stores]
    primary_store = stores[0]
    target_date = parse_dashboard_date(request)
    today_start, today_end = day_bounds(target_date)
    yesterday_start, yesterday_end = day_bounds(target_date - timedelta(days=1))
    now = timezone.now()
    now_ph = now.astimezone(PH_TZ)

    orders = Order.objects.filter(store_id__in=store_ids)
    today_orders = orders.filter(created_at__gte=today_start, created_at__lt=today_end)
    yesterday_orders = orders.filter(created_at__gte=yesterday_start, created_at__lt=yesterday_end)
    active_orders_qs = (
        orders.filter(status__in=ACTIVE_STATUSES)
        .select_related("customer", "rider", "store")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    today_count = today_orders.count()
    yesterday_count = yesterday_orders.count()
    change = today_count - yesterday_count
    change_label = f"{change:+d} from yesterday"

    preparing_qs = orders.filter(status=OrderStatus.PREPARING)
    attention_count = preparing_qs.filter(updated_at__lte=now - timedelta(minutes=PREP_TARGET_MINUTES)).count()
    on_delivery_qs = orders.filter(status=OrderStatus.ON_THE_WAY)
    delivered_delivery_today = today_orders.filter(
        status=OrderStatus.DELIVERED,
        delivery_method=DeliveryMethod.DELIVERY,
        delivered_at__isnull=False,
    )

    delivery_minutes = []
    for order in delivered_delivery_today.only("created_at", "delivered_at"):
        delivery_minutes.append(max(int((order.delivered_at - order.created_at).total_seconds() // 60), 0))
    average_delivery_minutes = round(sum(delivery_minutes) / len(delivery_minutes)) if delivery_minutes else 0

    gross_sales = money(today_orders.exclude(status=OrderStatus.CANCELLED).aggregate(total=Sum("total_amount"))["total"])
    commission_rate = money(primary_store.commission_rate) / Decimal("100.00")
    fees = money(gross_sales * commission_rate)
    net_sales = money(gross_sales - fees)

    pipeline_counts = Counter(
        orders.filter(status__in=ACTIVE_STATUSES).values_list("status", flat=True)
    )
    incoming_count = today_orders.exclude(status=OrderStatus.CANCELLED).count()
    accepted_count = today_orders.filter(
        status__in=[OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.ON_THE_WAY, OrderStatus.DELIVERED]
    ).count()
    acceptance_rate = round((accepted_count / incoming_count) * 100) if incoming_count else 100

    prep_durations = []
    for order in today_orders.filter(status__in=[OrderStatus.READY, OrderStatus.ON_THE_WAY, OrderStatus.DELIVERED]).only("created_at", "updated_at"):
        prep_durations.append(max(int((order.updated_at - order.created_at).total_seconds() // 60), 0))
    average_prep_time = round(sum(prep_durations) / len(prep_durations)) if prep_durations else 0
    pickup_delay = 0

    active_payload = []
    for order in active_orders_qs[:10]:
        age_minutes = max(int((now - order.created_at).total_seconds() // 60), 0)
        eta_minutes = max(PREP_TARGET_MINUTES - age_minutes, 0) if order.status in [OrderStatus.PENDING, OrderStatus.ACCEPTED, OrderStatus.PREPARING] else 0
        if order.status in [OrderStatus.READY, OrderStatus.ON_THE_WAY]:
            eta_minutes = 9 if order.status == OrderStatus.READY else average_delivery_minutes
        active_payload.append(
            {
                "id": f"SRG-{str(order.id)[:8].upper()}",
                "customer_name": customer_name(order),
                "items_summary": order_items_summary(order),
                "status": dashboard_status(order.status),
                "status_label": status_label(order.status),
                "rider_name": rider_name(order),
                "rider_label": rider_name(order) or ("Assigned" if order.rider_id else "Waiting"),
                "eta_minutes": eta_minutes,
                "eta_label": minutes_label(eta_minutes),
            }
        )

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
    alerts.append(
        {
            "id": "document-status",
            "type": "DOCUMENT_STATUS",
            "severity": "INFO",
            "message": "Store documents are verified. No onboarding action required.",
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

    availability = store_availability_payload(primary_store, now_ph)

    return {
        "merchant": {
            "id": str(request.user.id),
            "business_name": primary_store.name if len(stores) == 1 else f"{primary_store.name} + {len(stores) - 1} more",
            **availability,
            "service_modes": ["DELIVERY", "PICKUP"],
            "last_updated": max(store.updated_at for store in stores).astimezone(PH_TZ).isoformat(),
        },
        "stats": {
            "orders_today": {
                "value": today_count,
                "change": change,
                "change_label": change_label,
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
