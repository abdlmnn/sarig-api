# Locations API

Backend location helpers for address search, reverse geocoding, route estimates, and delivery fee estimates.

Frontend/mobile should call these endpoints instead of calling Geoapify or OpenRouteService directly.

## Environment

```env
GEOAPIFY_API_KEY=your_geoapify_api_key_here
OPENROUTESERVICE_API_KEY=your_openrouteservice_api_key_here
LOCATION_ENABLE_EXTERNAL_APIS=True
LOCATION_PROVIDER_TIMEOUT_SECONDS=8
LOCATION_COUNTRY_CODES=ph
LOCATION_BIAS_LATITUDE=8.003400
LOCATION_BIAS_LONGITUDE=124.283900
DELIVERY_BASE_FEE=40.00
DELIVERY_PER_KM_FEE=10.00
DELIVERY_MIN_FEE=40.00
DELIVERY_MAX_DISTANCE_KM=30
```

## Search Address

`GET /api/v1/locations/search/?q=MSU%20Main%20Gate`

Returns address suggestions from Geoapify.

```json
{
  "results": [
    {
      "address": "MSU Main Gate, Marawi City",
      "latitude": 8.0034,
      "longitude": 124.2839,
      "barangay": "Dimalna",
      "city": "Marawi City",
      "province": "Lanao del Sur",
      "postcode": "",
      "provider": "geoapify"
    }
  ]
}
```

## Reverse Geocode

`POST /api/v1/locations/reverse/`

```json
{
  "latitude": "8.003400",
  "longitude": "124.283900"
}
```

Returns a readable address for a pinned coordinate.

## Route Estimate

`POST /api/v1/locations/route-estimate/`

```json
{
  "origin": {
    "latitude": "8.010000",
    "longitude": "124.290000"
  },
  "destination": {
    "latitude": "8.003400",
    "longitude": "124.283900"
  }
}
```

Returns road distance/time from OpenRouteService when available. Falls back to Haversine estimate if routing is unavailable.

```json
{
  "distance_km": "2.40",
  "duration_minutes": 8,
  "provider": "openrouteservice",
  "route_geometry": "encoded-route"
}
```

## Delivery Fee Estimate

`POST /api/v1/locations/delivery-fee-estimate/`

```json
{
  "store": {
    "latitude": "8.010000",
    "longitude": "124.290000"
  },
  "customer": {
    "latitude": "8.003400",
    "longitude": "124.283900"
  }
}
```

```json
{
  "distance_km": "2.40",
  "duration_minutes": 8,
  "provider": "openrouteservice",
  "route_geometry": null,
  "delivery_fee": "64.00"
}
```

Checkout must still recalculate the delivery fee server-side.
