from decimal import Decimal, ROUND_HALF_UP
import logging

import requests
from django.conf import settings

from apps.common.money import money
from apps.riders.services import RiderDispatcherService

logger = logging.getLogger(__name__)

MARAWI_BOUNDS = {
    "min_latitude": Decimal("7.930000"),
    "max_latitude": Decimal("8.080000"),
    "min_longitude": Decimal("124.230000"),
    "max_longitude": Decimal("124.360000"),
}


class LocationProviderError(Exception):
    pass


def _provider_enabled(api_key):
    return bool(api_key) and getattr(settings, "LOCATION_ENABLE_EXTERNAL_APIS", True)


def _timeout():
    return getattr(settings, "LOCATION_PROVIDER_TIMEOUT_SECONDS", 8)


def is_inside_marawi(latitude, longitude):
    latitude = Decimal(str(latitude))
    longitude = Decimal(str(longitude))
    return (
        MARAWI_BOUNDS["min_latitude"] <= latitude <= MARAWI_BOUNDS["max_latitude"]
        and MARAWI_BOUNDS["min_longitude"] <= longitude <= MARAWI_BOUNDS["max_longitude"]
    )


def calculate_delivery_fee(distance_km):
    base_fee = Decimal(str(settings.DELIVERY_BASE_FEE))
    per_km_fee = Decimal(str(settings.DELIVERY_PER_KM_FEE))
    min_fee = Decimal(str(settings.DELIVERY_MIN_FEE))
    fee = base_fee + (money(Decimal(str(distance_km))) * per_km_fee)
    return max(money(fee), money(min_fee))


def haversine_route_estimate(origin, destination):
    distance_km = RiderDispatcherService.haversine(
        float(origin["longitude"]),
        float(origin["latitude"]),
        float(destination["longitude"]),
        float(destination["latitude"]),
    )
    road_distance_km = round(distance_km * 1.3, 2)
    duration_minutes = round((road_distance_km / 30) * 60)
    return {
        "distance_km": Decimal(str(road_distance_km)).quantize(Decimal("0.01")),
        "duration_minutes": max(duration_minutes, 1),
        "provider": "haversine_fallback",
        "route_geometry": None,
    }


class GeoapifyService:
    GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
    REVERSE_URL = "https://api.geoapify.com/v1/geocode/reverse"

    @classmethod
    def search(cls, query, limit=5):
        api_key = settings.GEOAPIFY_API_KEY
        if not _provider_enabled(api_key):
            raise LocationProviderError("Geoapify API key is not configured.")

        params = {
            "text": query,
            "limit": limit,
            "apiKey": api_key,
        }
        country_codes = getattr(settings, "LOCATION_COUNTRY_CODES", "")
        if country_codes:
            params["filter"] = f"countrycode:{country_codes}"

        bias_lat = getattr(settings, "LOCATION_BIAS_LATITUDE", "")
        bias_lng = getattr(settings, "LOCATION_BIAS_LONGITUDE", "")
        if bias_lat and bias_lng:
            params["bias"] = f"proximity:{bias_lng},{bias_lat}"

        response = requests.get(
            cls.GEOCODE_URL,
            params=params,
            timeout=_timeout(),
        )
        response.raise_for_status()
        results = [
            cls._feature_to_location(feature)
            for feature in response.json().get("features", [])
        ]
        return [
            result
            for result in results
            if result["latitude"] is not None
            and result["longitude"] is not None
            and is_inside_marawi(result["latitude"], result["longitude"])
        ]

    @classmethod
    def reverse(cls, latitude, longitude):
        api_key = settings.GEOAPIFY_API_KEY
        if not _provider_enabled(api_key):
            raise LocationProviderError("Geoapify API key is not configured.")

        response = requests.get(
            cls.REVERSE_URL,
            params={
                "lat": latitude,
                "lon": longitude,
                "apiKey": api_key,
            },
            timeout=_timeout(),
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        if not features:
            return None
        return cls._feature_to_location(features[0])

    @staticmethod
    def _feature_to_location(feature):
        props = feature.get("properties", {})
        address = props.get("formatted") or props.get("address_line1") or ""
        return {
            "address": address,
            "address_text": address,
            "latitude": props.get("lat"),
            "longitude": props.get("lon"),
            "barangay": props.get("suburb") or props.get("district") or "",
            "city": props.get("city") or props.get("municipality") or "",
            "province": props.get("state") or "",
            "postal_code": props.get("postcode") or "",
            "provider": "geoapify",
        }


class OpenRouteService:
    DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

    @classmethod
    def route_estimate(cls, origin, destination):
        api_key = settings.OPENROUTESERVICE_API_KEY
        if not _provider_enabled(api_key):
            raise LocationProviderError("OpenRouteService API key is not configured.")

        response = requests.post(
            cls.DIRECTIONS_URL,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json={
                "coordinates": [
                    [float(origin["longitude"]), float(origin["latitude"])],
                    [float(destination["longitude"]), float(destination["latitude"])],
                ],
                "instructions": False,
            },
            timeout=_timeout(),
        )
        response.raise_for_status()
        routes = response.json().get("routes", [])
        if not routes:
            raise LocationProviderError("OpenRouteService returned no route.")

        route = routes[0]
        summary = route.get("summary", {})
        distance_km = Decimal(str(summary.get("distance", 0))) / Decimal("1000")
        duration_minutes = int(round(float(summary.get("duration", 0)) / 60))
        return {
            "distance_km": distance_km.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "duration_minutes": max(duration_minutes, 1),
            "provider": "openrouteservice",
            "route_geometry": route.get("geometry"),
        }


def route_estimate(origin, destination):
    try:
        return OpenRouteService.route_estimate(origin, destination)
    except (LocationProviderError, requests.RequestException, ValueError, KeyError) as exc:
        message = str(exc)
        if isinstance(exc, LocationProviderError) and "API key is not configured" in message:
            logger.debug("Route provider fallback used: %s", exc)
        else:
            logger.warning("Route provider fallback used: %s", exc)
        return haversine_route_estimate(origin, destination)
