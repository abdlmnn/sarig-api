from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apps.vendors.models import StoreManualOverride


PH_TZ = ZoneInfo("Asia/Manila")
DAY_KEYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


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
    defaults = default_business_hours()
    hours = store.business_hours or defaults
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
    return [by_day.get(day, defaults[index]) for index, day in enumerate(DAY_KEYS)]


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
