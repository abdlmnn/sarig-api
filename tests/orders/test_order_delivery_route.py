from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.models import DeliveryMethod, Order, OrderStatus
from apps.riders.models import RiderProfile
from apps.users.models import User
from apps.vendors.models import BusinessVertical, Store


class OrderDeliveryRouteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="route-customer",
            email="route-customer@test.com",
            password="pw12345",
        )
        self.merchant = User.objects.create_user(
            username="route-merchant",
            email="route-merchant@test.com",
            password="pw12345",
        )
        self.rider = User.objects.create_user(
            username="route-rider",
            email="route-rider@test.com",
            password="pw12345",
        )
        vertical = BusinessVertical.objects.create(name="Route Store", slug="route-store")
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Route Store",
            latitude=Decimal("8.010000"),
            longitude=Decimal("124.290000"),
            street_address="Route Street",
            city="Marawi",
        )
        self.rider_profile = RiderProfile.objects.create(
            user=self.rider,
            current_latitude=Decimal("8.010041"),
            current_longitude=Decimal("124.290012"),
        )
        self.order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            rider=self.rider,
            delivery_method=DeliveryMethod.DELIVERY,
            status=OrderStatus.ON_THE_WAY,
            delivery_address_text="Customer destination",
            delivery_latitude=Decimal("8.003400"),
            delivery_longitude=Decimal("124.283900"),
            subtotal=Decimal("100.00"),
            delivery_fee=Decimal("40.00"),
            system_fee=Decimal("10.00"),
            total_amount=Decimal("150.00"),
        )

    @patch("apps.orders.views.route_geojson")
    def test_customer_receives_real_road_geometry(self, route_service):
        route_service.return_value = {
            "provider": "openrouteservice",
            "distance_km": Decimal("2.40"),
            "duration_minutes": 8,
            "route_geometry": {
                "type": "LineString",
                "coordinates": [[124.290012, 8.010041], [124.283900, 8.003400]],
            },
        }
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(f"/api/v1/orders/{self.order.id}/delivery-route/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["geometry"]["type"], "LineString")
        self.assertEqual(response.data["properties"]["route_status"], "AVAILABLE")
        route_service.assert_called_once_with(
            {
                "latitude": self.rider_profile.current_latitude,
                "longitude": self.rider_profile.current_longitude,
            },
            {
                "latitude": self.order.delivery_latitude,
                "longitude": self.order.delivery_longitude,
            },
        )

    @patch("apps.orders.views.route_geojson")
    def test_provider_fallback_does_not_claim_straight_line_is_road_route(self, route_service):
        route_service.return_value = {
            "provider": "haversine_fallback",
            "distance_km": Decimal("2.10"),
            "duration_minutes": 5,
            "route_geometry": None,
        }
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(f"/api/v1/orders/{self.order.id}/delivery-route/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["geometry"])
        self.assertEqual(response.data["properties"]["route_status"], "DEGRADED")

    def test_unrelated_user_cannot_access_route(self):
        other_user = User.objects.create_user(
            username="other-route-user",
            email="other-route-user@test.com",
            password="pw12345",
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.get(f"/api/v1/orders/{self.order.id}/delivery-route/")

        self.assertEqual(response.status_code, 404)

    @patch("apps.orders.views.route_geojson")
    def test_route_requires_active_delivery(self, route_service):
        self.order.status = OrderStatus.DELIVERED
        self.order.save(update_fields=["status"])
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(f"/api/v1/orders/{self.order.id}/delivery-route/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "route_not_active")
        route_service.assert_not_called()
