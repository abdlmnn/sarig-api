# Admin Dashboard and Marawi Zones Frontend API Contract

This document is the frontend-facing contract for the admin dashboard and Marawi service zones.

Use this as the source of truth for:

- which endpoints the frontend should call
- which query params and request bodies to send
- which response fields the UI should expect
- which values are stable and should not be renamed

All endpoints are under:

`/api/v1/operations`

All admin endpoints require admin authentication.

---

## Response Format

Success:

```json
{
  "success": true,
  "message": "Request successful",
  "data": {}
}
```

Paginated list:

```json
{
  "success": true,
  "message": "Request successful",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 0,
      "total_pages": 0
    }
  }
}
```

Validation error:

```json
{
  "success": false,
  "message": "Validation failed",
  "errors": {
    "field_name": ["This field is required."]
  }
}
```

---

## Authentication

The frontend should send the same auth it already uses for protected API calls.

Recommended client behavior:

- attach the auth token or session cookie on every request
- treat `403` as a hard permission failure
- treat `401` as expired or missing auth

---

## 1. Admin Dashboard

### `GET /api/v1/operations/dashboard`

Use this for the dashboard homepage.

Query params:

- `date_from` optional ISO date
- `date_to` optional ISO date
- `zone_id` optional UUID

Request example:

```http
GET /api/v1/operations/dashboard?date_from=2026-06-01&date_to=2026-06-23
```

Response fields:

- `stats.gmv.amount`
- `stats.gmv.currency`
- `stats.gmv.change_percent`
- `stats.revenue.amount`
- `stats.revenue.currency`
- `stats.revenue.change_percent`
- `stats.orders.total`
- `stats.orders.live`
- `stats.trips.total`
- `stats.trips.live`
- `stats.reviews.pending`
- `service_zones.map_center.label`
- `service_zones.map_center.latitude`
- `service_zones.map_center.longitude`
- `service_zones.zones[]`
- `onboarding_summary.merchant_pending`
- `onboarding_summary.merchant_ready`
- `onboarding_summary.rider_pending`
- `onboarding_summary.rider_ready`
- `onboarding_summary.changes_requested`
- `onboarding_summary.approved_today`
- `latest_applications.merchant[]`
- `latest_applications.rider[]`
- `finance.revenue_streams[]`
- `marketing.new_customers`
- `marketing.new_customers_delta`
- `marketing.repeat_orders_percent`
- `marketing.repeat_orders_change_percent`
- `marketing.promo_spend.amount`
- `marketing.promo_spend.currency`
- `marketing.promo_spend.status`
- `system_watch[]`
- `last_updated_at`

Zone item fields in the dashboard:

- `id`
- `name`
- `orders`
- `active_riders`
- `average_delay_minutes`
- `load_status`

---

## 2. Marawi Service Zones

### `GET /api/v1/operations/service-zones/`

Use this for the Marawi map and zone list.

Query params:

- `city` optional, default `Marawi`
- `status` optional, `STABLE`, `HIGH`, or `WATCH`
- `include_inactive` optional boolean

Request example:

```http
GET /api/v1/operations/service-zones/?city=Marawi&status=WATCH
```

Response fields:

- `city`
- `updated_at`
- `map.center_latitude`
- `map.center_longitude`
- `map.zoom`
- `summary.zones`
- `summary.active_orders`
- `summary.active_transport_bookings`
- `summary.available_riders`
- `summary.watch_zones`
- `zones[]`

Zone item fields:

- `id`
- `name`
- `slug`
- `city`
- `province`
- `load_status`
- `active_orders`
- `active_transport_bookings`
- `available_riders`
- `active_riders`
- `approved_merchants`
- `average_delay_minutes`
- `center_latitude`
- `center_longitude`
- `boundary`
- `last_updated_at`

Allowed `load_status` values:

- `STABLE`
- `HIGH`
- `WATCH`

Frontend usage:

- render the Marawi map centered on `map.center_latitude` and `map.center_longitude`
- color zones by `load_status`
- show counts for orders, riders, merchants, and delay
- use `boundary` if present, otherwise use the center coordinates

---

### `GET /api/v1/operations/service-zones/{zone_id}/`

Use this when the admin clicks a zone.

Response fields:

- `zone`
- `metrics`
- `recent_orders[]`
- `active_transport_bookings[]`
- `active_riders[]`
- `busy_merchants[]`

Zone object fields:

- `id`
- `name`
- `slug`
- `city`
- `province`
- `center_latitude`
- `center_longitude`
- `barangay_names`
- `boundary`
- `is_active`

Recommended UI use:

- show a detail side panel
- show the zone status and summary counts
- list recent orders and riders
- show busy merchants in the selected zone

---

### `GET /api/v1/operations/service-zones/{zone_id}/merchants/`

Use this to populate the zone merchant list.

Query params:

- `page`
- `page_size`

Merchant item fields:

- `id`
- `store_name`
- `branch_name`
- `owner_name`
- `email`
- `contact_number`
- `status`
- `zone`
- `is_open`
- `rating`
- `total_orders`
- `active_orders`
- `gmv_amount`
- `latitude`
- `longitude`
- `created_at`

---

### `GET /api/v1/operations/service-zones/{zone_id}/riders/`

Use this to populate the zone rider list.

Query params:

- `page`
- `page_size`

Rider item fields:

- `id`
- `full_name`
- `email`
- `contact_number`
- `status`
- `vehicle_type`
- `plate_number`
- `zone`
- `is_available`
- `completed_deliveries`
- `completed_trips`
- `wallet_balance`
- `current_latitude`
- `current_longitude`
- `last_location_update_at`

Allowed rider `status` values:

- `offline`
- `online`
- `busy`

---

### `GET /api/v1/operations/service-zones/{zone_id}/activity/`

Use this for the zone activity timeline panel.

Response fields:

- `events[]`

Event item fields:

- `id`
- `type`
- `actor_type`
- `actor_name`
- `description`
- `created_at`

---

## 3. Onboarding

### `GET /api/v1/onboarding/applications/`

Use this for the onboarding table and summary cards. The list response includes `totals`.

Totals fields:

- `merchants`
- `riders`
- `ready`
- `changes`
- `request_changes`

### `POST /api/v1/onboarding/applications/{application_id}/approve/`

Use this to approve an application.

### `POST /api/v1/onboarding/applications/{application_id}/request-changes/`

Use this to request applicant changes.

```json
{
  "admin_remarks": "Please upload clearer documents.",
  "requested_fields": ["nbi_clearance"]
}
```

### `POST /api/v1/onboarding/applications/{application_id}/reject/`

Use this to reject an application.

Allowed `decision` values:

- `approved`
- `changes_requested`
- `rejected`

If requesting changes, send:

```json
{
  "decision": "changes_requested",
  "admin_notes": "Please update the missing permit.",
  "change_requests": [
    {
      "field": "mayors_permit",
      "reason": "Missing file"
    }
  ]
}
```

Response fields:

- `id`
- `status`
- `reviewed_at`

Returned `status` values:

- `approved`
- `changes_requested`
- `rejected`

---

## 4. Merchants

### `GET /api/v1/operations/merchants`

Use this for the merchant admin table.

Query params:

- `status`
- `search`
- `zone_id`
- `page`
- `page_size`

Merchant item fields:

- `id`
- `store_name`
- `branch_name`
- `owner_name`
- `email`
- `contact_number`
- `status`
- `zone`
- `is_open`
- `rating`
- `total_orders`
- `active_orders`
- `gmv_amount`
- `latitude`
- `longitude`
- `created_at`

Allowed `status` values:

- `active`
- `paused`
- `suspended`

---

## 5. Riders

### `GET /api/v1/operations/riders`

Use this for the rider admin table.

Query params:

- `status`
- `vehicle_type`
- `zone_id`
- `search`
- `page`
- `page_size`

Rider item fields:

- `id`
- `full_name`
- `email`
- `contact_number`
- `status`
- `vehicle_type`
- `plate_number`
- `zone`
- `is_available`
- `completed_deliveries`
- `completed_trips`
- `wallet_balance`
- `current_latitude`
- `current_longitude`
- `last_location_update_at`

---

## 6. Finance

### `GET /api/v1/operations/finance/overview`

Use this for finance summary cards.

Query params:

- `date_from`
- `date_to`

Response fields:

- `gmv`
- `platform_revenue`
- `merchant_fees`
- `delivery_fees`
- `transport_fees`
- `pending_payouts_count`
- `pending_payouts_amount`
- `currency`

---

## 7. Marketing

### `GET /api/v1/operations/marketing/overview`

Use this for the marketing summary area.

Response fields:

- `new_customers`
- `new_customers_delta`
- `repeat_orders_percent`
- `repeat_orders_change_percent`
- `promo_spend.amount`
- `promo_spend.currency`
- `promo_spend.status`
- `active_campaigns`
- `active_promo_codes`
- `currency`

---

## 8. Alerts

### `GET /api/v1/operations/system/alerts`

Use this for the system watch panel.

Query params:

- `severity`
- `is_resolved`
- `page`
- `page_size`

Alert item fields:

- `id`
- `severity`
- `title`
- `message`
- `source`
- `is_resolved`
- `created_at`

Allowed `severity` values:

- `info`
- `warning`
- `critical`

### `PATCH /api/v1/operations/system/alerts/{alert_id}/resolve`

Use this to resolve an alert.

Response fields:

- `id`
- `severity`
- `title`
- `message`
- `source`
- `is_resolved`
- `created_at`

---

## Frontend Rules

- Use `admin/dashboard` for the command center homepage.
- Use `service-zones` for the Marawi map and operations panel.
- Use the zone detail endpoint when the user clicks a zone.
- Use `merchants` and `riders` for admin tables and filters.
- Use `onboarding/applications/` for review lists and totals, then use the dedicated approve, request-changes, and reject endpoints for actions.
- Do not hardcode zone names in the frontend if the API already provides them.
- Treat `load_status` as the visual source of truth.
- Treat `center_latitude` and `center_longitude` as the fallback map placement when no boundary exists.

---

## Notes For The Frontend Team

- `ServiceZone` is an operations grouping, not a merchant or customer object.
- `boundary` may be empty in MVP data.
- `zone_id` is a UUID string.
- The dashboard endpoint already returns enough data for the first screen.
- The zone detail endpoint should be used for drill-down, not for initial page load.
