from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(
    GEOAPIFY_API_KEY="geo-key",
    OPENROUTESERVICE_API_KEY="ors-key",
    LOCATION_ENABLE_EXTERNAL_APIS=True,
)
class LocationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("apps.locations.services.requests.get")
    def test_search_returns_geoapify_results(self, mock_get):
        mock_get.return_value.json.return_value = {
            "features": [
                {
                    "properties": {
                        "formatted": "MSU Main Gate, Marawi City",
                        "lat": 8.0034,
                        "lon": 124.2839,
                        "city": "Marawi City",
                    }
                }
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        res = self.client.get("/api/v1/locations/search/", {"q": "MSU Main Gate"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["results"][0]["address"], "MSU Main Gate, Marawi City")
        self.assertEqual(res.data["results"][0]["provider"], "geoapify")
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["filter"], "countrycode:ph")
        self.assertEqual(params["bias"], "proximity:124.283900,8.003400")

    @patch("apps.locations.services.requests.get")
    def test_reverse_returns_readable_address(self, mock_get):
        mock_get.return_value.json.return_value = {
            "features": [
                {
                    "properties": {
                        "formatted": "Near MSU Main Gate, Marawi City",
                        "lat": 8.0034,
                        "lon": 124.2839,
                        "suburb": "Dimalna",
                        "city": "Marawi City",
                    }
                }
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None

        res = self.client.post(
            "/api/v1/locations/reverse/",
            {"latitude": "8.003400", "longitude": "124.283900"},
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["barangay"], "Dimalna")

    @patch("apps.locations.services.requests.post")
    def test_route_estimate_returns_openrouteservice_distance(self, mock_post):
        mock_post.return_value.json.return_value = {
            "routes": [
                {
                    "summary": {"distance": 2400, "duration": 480},
                    "geometry": "encoded-route",
                }
            ]
        }
        mock_post.return_value.raise_for_status.return_value = None

        res = self.client.post(
            "/api/v1/locations/route-estimate/",
            {
                "origin": {"latitude": "8.010000", "longitude": "124.290000"},
                "destination": {"latitude": "8.003400", "longitude": "124.283900"},
            },
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["distance_km"], Decimal("2.40"))
        self.assertEqual(res.data["duration_minutes"], 8)
        self.assertEqual(res.data["provider"], "openrouteservice")

    @patch("apps.locations.services.requests.post")
    def test_delivery_fee_estimate_uses_route_distance(self, mock_post):
        mock_post.return_value.json.return_value = {
            "routes": [{"summary": {"distance": 2400, "duration": 480}}]
        }
        mock_post.return_value.raise_for_status.return_value = None

        res = self.client.post(
            "/api/v1/locations/delivery-fee-estimate/",
            {
                "store": {"latitude": "8.010000", "longitude": "124.290000"},
                "customer": {"latitude": "8.003400", "longitude": "124.283900"},
            },
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["distance_km"], Decimal("2.40"))
        self.assertEqual(res.data["delivery_fee"], Decimal("64.00"))

    @override_settings(DELIVERY_MAX_DISTANCE_KM=1)
    @patch("apps.locations.services.requests.post")
    def test_delivery_fee_estimate_rejects_far_distance(self, mock_post):
        mock_post.return_value.json.return_value = {
            "routes": [{"summary": {"distance": 2400, "duration": 480}}]
        }
        mock_post.return_value.raise_for_status.return_value = None

        res = self.client.post(
            "/api/v1/locations/delivery-fee-estimate/",
            {
                "store": {"latitude": "8.010000", "longitude": "124.290000"},
                "customer": {"latitude": "8.003400", "longitude": "124.283900"},
            },
            format="json",
        )

        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "Delivery address is outside the supported distance.")


@override_settings(
    OPENROUTESERVICE_API_KEY="",
    LOCATION_ENABLE_EXTERNAL_APIS=True,
)
class LocationFallbackTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_route_estimate_falls_back_without_ors_key(self):
        res = self.client.post(
            "/api/v1/locations/route-estimate/",
            {
                "origin": {"latitude": "8.003400", "longitude": "124.283900"},
                "destination": {"latitude": "8.003400", "longitude": "124.283900"},
            },
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["provider"], "haversine_fallback")
        self.assertEqual(res.data["distance_km"], Decimal("0.00"))
