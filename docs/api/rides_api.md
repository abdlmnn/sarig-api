# Rides API (v1)

Base URL:
`http://localhost:8000/api/v1/rides/`

Auth:
- All endpoints require JWT auth.

---

## Create Ride Request

### `POST /`
Create a new passenger ride request.

Request body:
```json
{
  "requested_vehicle_type": "MOTORCYCLE",
  "pickup_lat": "7.100000",
  "pickup_lng": "125.100000",
  "dropoff_lat": "7.200000",
  "dropoff_lng": "125.200000"
}
```

Notes:
- `requested_vehicle_type`: `MOTORCYCLE` or `CAR`
- Estimated fare and fare breakdown are generated automatically.

---

## List My Rides

### `GET /`
Returns rides based on user type:
- Passenger: own rides
- Rider: assigned rides
- Admin/staff: all rides

---

## Ride Detail

### `GET /{ride_id}/`
Returns one ride record (subject to access rules above).

---

## Assign Rider (Admin/System)

### `POST /{ride_id}/assign/`

Request body:
```json
{
  "rider_id": "UUID"
}
```

Rules:
- Admin/staff only.
- Ride must be `REQUESTED`.
- Rider must be:
  - online
  - available
  - `can_do_ride_hailing=true`
  - same vehicle type as request

Idempotent behavior:
- If ride already matched to the same rider, returns success without duplicate mutation.

Auto-matching:
- On ride creation, system can auto-assign nearest eligible rider when `JOYRIDE_ENABLE_AUTO_MATCHING=True`.
- Matching uses PostGIS distance when enabled, with Haversine fallback.

---

## Rider/Passenger Actions

### `POST /{ride_id}/accept/`
- Rider confirmation endpoint (assigned rider only).
- Does not change status from `MATCHED`; it confirms rider commitment and sets `rider_accepted_at`.
- Required before rider can call `arrive` or `start`.

### `POST /{ride_id}/arrive/`
- Sets status to `RIDER_ARRIVED`.
- Assigned rider only.

### `POST /{ride_id}/start/`
- Sets status to `IN_TRIP`.
- Assigned rider only.

### `POST /{ride_id}/complete/`
- Sets status to `COMPLETED`.
- Assigned rider only.
- Final fare is computed and stored.

### `POST /{ride_id}/cancel/`
- Sets status to `CANCELLED`.
- Passenger or assigned rider (or admin).

Optional body:
```json
{
  "cancel_reason": "Passenger changed plans"
}
```

Effects:
- `cancel_reason` and `cancelled_by` are stored.
- Assigned rider availability is restored.
- If assigned rider cancels after acceptance, penalty is applied and stored (`rider_cancel_penalty`).

---

## Generic Transition (Advanced/Internal)

### `POST /{ride_id}/transition/`

Request body:
```json
{
  "status": "MATCHED"
}
```

Use only if needed for internal tools. Frontend should prefer explicit endpoints above.

---

## Status Lifecycle

Main flow:
`REQUESTED -> MATCHED -> RIDER_ARRIVED -> IN_TRIP -> COMPLETED`

Other valid transitions:
- `REQUESTED -> EXPIRED`
- `REQUESTED|MATCHED|RIDER_ARRIVED -> CANCELLED`

---

## Timeout Expiration

Command:
- `python manage.py expire_pending_rides`

Scheduler:
- Celery Beat runs expiration task every minute.
- Config uses `JOYRIDE_REQUEST_TIMEOUT_MINUTES` (default `5`).

---

## Fare Model (Current)

Fare is calculated as:
- `base_fare + distance_fare + time_fare`
- optional surge multiplier if enabled

Stored in:
- `Ride.estimated_fare`
- `Ride.final_fare`
- `FareBreakdown` record per ride

---

## Errors (Common)

- `400`: invalid transition, rider eligibility mismatch, vehicle mismatch
- `403`: forbidden action (example: non-admin assign)
- `404`: ride not visible to current user or rider not found

---

## WebSocket Realtime (Ride Events)

Endpoint:
- `ws/rides/`

Auth:
- Uses authenticated session/JWT context from Channels auth middleware.
- Unauthenticated connections are rejected.

Who receives events:
- Passenger of the ride
- Assigned rider of the ride

Backend groups:
- `user_{passenger_id}_rides`
- `user_{rider_user_id}_rides`

Event shape:
```json
{
  "type": "STATUS_IN_TRIP",
  "ride_id": "UUID",
  "status": "IN_TRIP",
  "payload": {
    "status": "IN_TRIP"
  }
}
```

Common event types:
- `RIDE_REQUESTED`
- `RIDE_AUTO_ASSIGNED`
- `RIDE_ASSIGNED`
- `RIDER_ACCEPTED`
- `STATUS_MATCHED`
- `STATUS_RIDER_ARRIVED`
- `STATUS_IN_TRIP`
- `STATUS_COMPLETED`
- `STATUS_CANCELLED`
- `STATUS_EXPIRED`

Sample events:

1. Ride requested
```json
{
  "type": "RIDE_REQUESTED",
  "ride_id": "f4d0...a2",
  "status": "REQUESTED",
  "payload": {
    "status": "REQUESTED"
  }
}
```

2. Auto-assigned rider
```json
{
  "type": "RIDE_AUTO_ASSIGNED",
  "ride_id": "f4d0...a2",
  "status": "MATCHED",
  "payload": {
    "status": "MATCHED",
    "rider_id": "7e21...bb"
  }
}
```

3. Ride cancelled with reason
```json
{
  "type": "STATUS_CANCELLED",
  "ride_id": "f4d0...a2",
  "status": "CANCELLED",
  "payload": {
    "status": "CANCELLED",
    "cancel_reason": "Passenger changed plans"
  }
}
```

Frontend fallback:
- Keep REST polling fallback (`GET /api/v1/rides/` or `GET /api/v1/rides/{id}/`) in case websocket disconnects.

---

## Ride Chat (In-App)

REST history endpoint:
- `GET /api/v1/chat/ride-history/{ride_id}/`

Response includes:
- `chat_locked` (true when ride is `COMPLETED`, `CANCELLED`, or `EXPIRED`)
- `contact_info` (name + phone number)
- `messages`

WebSocket endpoint:
- `ws/ride-chat/{ride_id}/`

Rules:
- only ride passenger and assigned rider can connect
- message sending is blocked when ride is terminal (chat lock)
