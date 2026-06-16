# Riders API

The Riders API handles rider profiles, real-time location tracking, dispatcher assignment, and wallet earnings.

## Endpoints

### 1. Toggle Online Status
`POST /api/v1/riders/status/`
- Toggles the rider's `is_online` status. Required to receive orders.

### 2. Update Location
`POST /api/v1/riders/location/`
- Updates `current_latitude` and `current_longitude`.
- If the rider is currently on a delivery (`ON_THE_WAY`), this endpoint automatically calculates the new ETA and broadcasts it to the customer via WebSockets.

### 3. Order Action
`POST /api/v1/riders/order/<uuid:order_id>/`
- Actions: `pickup`, `delivered`.
- Security: Only the assigned rider can perform these actions.
- Automatically processes earnings to the rider's wallet upon `delivered`.

### 4. Rider Dashboard
`GET /api/v1/riders/dashboard/`
- Returns rider statistics, total deliveries, and current wallet balance.

## Background Services
* `RiderDispatcherService`: Uses the Haversine formula to find the nearest available rider and calculates accurate road ETAs (1.3x multiplier).
