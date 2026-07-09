# Merchant Dashboard API

The frontend dashboard composes merchant store state and order metrics from separate app-owned APIs.

## Merchant Store Overview

`GET /api/v1/merchant/dashboard/overview/`

Auth:
`Merchant bearer token required`

Purpose:
Return merchant/store availability only. The merchant is inferred from the authenticated user; frontend must not send merchant or store IDs.

Response sections:

```text
merchant
```

## Store Order Activity

`GET /api/v1/orders/store-activity/`

Auth:
`Merchant bearer token required`

Purpose:
Return order activity for the authenticated user's active stores.

Optional query params:

```text
date=YYYY-MM-DD
range=today
range=week
```

Current behavior:
- defaults to today in Philippines timezone
- `date` is supported
- `range` is reserved for future extension

Response sections:

```text
stats
order_pipeline
active_orders
service_health
alerts
settlement
delivery_lanes
```

Notes:
- Money values include raw decimal strings, currency, and formatted labels.
- Time values include raw minutes and display labels where relevant.
- Financial totals are calculated by the backend.
- Current schema does not yet store exact order status transition timestamps, so `average_prep_time` and `pickup_delay` use safe fallbacks until order event history exists.

## Demo Data

For local frontend development, seed a populated merchant dashboard:

```bash
python manage.py seed_merchant_dashboard_demo
```

Seeded merchant login:

```text
username: demo_merchant
password: Password123!
```

The command creates:
- one active restaurant merchant/store
- 16 food products across menu categories
- demo customers and riders
- many today and yesterday orders across new, accepted, preparing, ready, on-delivery, delivered, and cancelled states
- delivery lane data for Marawi areas

The command is repeatable. By default it replaces only the demo store's products/categories/orders. Use `--append` if you want to add more orders instead.

Example:

```json
{
  "stats": {
    "orders_today": {
      "value": 4,
      "change": 1,
      "change_label": "+1 from yesterday"
    },
    "preparing_now": {
      "value": 1,
      "attention_count": 0,
      "note": "0 need attention"
    },
    "on_delivery": {
      "value": 0,
      "average_delivery_minutes": 0,
      "note": "Average 0 min"
    },
    "net_sales": {
      "value": "892.50",
      "currency": "PHP",
      "formatted": "₱892",
      "note": "After service fees"
    }
  },
  "order_pipeline": {
    "new": 1,
    "accepted": 0,
    "preparing": 1,
    "ready": 1,
    "assigned": 0
  },
  "active_orders": [],
  "service_health": {
    "acceptance_rate": {
      "value": 100,
      "formatted": "100%",
      "status": "STRONG",
      "label": "Strong"
    },
    "average_prep_time": {
      "value_minutes": 0,
      "formatted": "0m",
      "target_minutes": 15,
      "note": "Target 15m"
    },
    "pickup_delay": {
      "value_minutes": 0,
      "formatted": "0m",
      "status": "STABLE",
      "label": "Stable"
    }
  },
  "alerts": [
    {
      "id": "document-status",
      "type": "DOCUMENT_STATUS",
      "severity": "INFO",
      "message": "Store documents are verified. No onboarding action required."
    }
  ],
  "settlement": {
    "gross_sales": {
      "value": "1050.00",
      "currency": "PHP",
      "formatted": "₱1,050"
    },
    "fees": {
      "value": "157.50",
      "currency": "PHP",
      "formatted": "₱158"
    },
    "expected_payout": {
      "value": "892.50",
      "currency": "PHP",
      "formatted": "₱892"
    },
    "next_settlement_window": {
      "datetime": "2026-07-03T10:00:00+08:00",
      "label": "Tomorrow, 10:00 AM"
    }
  },
  "delivery_lanes": []
}
```
