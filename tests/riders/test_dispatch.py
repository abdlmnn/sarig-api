from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from apps.catalog.models import Category, Product
from apps.orders.models import DeliveryMethod, Order, OrderStatus
from apps.riders.models import RiderOrderOffer, RiderOrderOfferStatus, RiderProfile
from apps.riders.services import RiderDispatcherService
from apps.users.models import User
from apps.vendors.models import BusinessVertical, Store


class RiderDispatcherTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="customer", email="customer@test.com", password="pw12345")
        self.merchant = User.objects.create_user(username="merchant", email="merchant@test.com", password="pw12345")
        self.rider_user = User.objects.create_user(username="rider", email="rider@test.com", password="pw12345")
        self.other_rider_user = User.objects.create_user(
            username="other-rider", email="other-rider@test.com", password="pw12345"
        )
        vertical, _ = BusinessVertical.objects.get_or_create(slug="restaurant", defaults={"name": "Restaurant"})
        self.store = Store.objects.create(
            owner=self.merchant,
            vertical=vertical,
            name="Dispatch Store",
            latitude=7.190700,
            longitude=125.455300,
            street_address="Dispatch St",
            city="Marawi",
        )
        self.category = Category.objects.create(store=self.store, name="Meals", slug="meals")
        self.product = Product.objects.create(
            category=self.category,
            name="Burger",
            price=Decimal("100.00"),
            preparation_time_minutes=8,
        )

    def test_haversine_distance_calculation(self):
        distance = RiderDispatcherService.haversine(125.4553, 7.1907, 125.4553, 7.1907)
        self.assertEqual(distance, 0.0)

    def test_rider_assignment_selects_nearest_available_rider(self):
        near_user = User.objects.create_user(username="near", email="near@test.com", password="pw12345")
        far_user = User.objects.create_user(username="far", email="far@test.com", password="pw12345")

        near = RiderProfile.objects.create(
            user=near_user,
            is_online=True,
            is_available=True,
            can_do_delivery=True,
            current_latitude=7.190700,
            current_longitude=125.455300,
        )
        RiderProfile.objects.create(
            user=far_user,
            is_online=True,
            is_available=True,
            can_do_delivery=True,
            current_latitude=7.290700,
            current_longitude=125.555300,
        )

        best, _ = RiderDispatcherService.find_best_rider(7.190700, 125.455300, max_radius_km=20)
        self.assertIsNotNone(best)
        self.assertEqual(best.id, near.id)

    @patch("apps.riders.services.RiderDispatcherService.notify_rider_delivery_offer")
    def test_pre_dispatch_creates_offer_without_assigning_rider(self, notify_offer):
        rider = self.create_available_rider()
        order = self.create_order(status=OrderStatus.PREPARING)

        offer = RiderDispatcherService.maybe_pre_dispatch_order(order)

        self.assertIsNotNone(offer)
        self.assertEqual(offer.rider_id, rider.id)
        order.refresh_from_db()
        self.assertIsNone(order.rider_id)
        self.assertEqual(RiderOrderOffer.objects.filter(order=order).count(), 1)
        notify_offer.assert_called_once()

    @patch("apps.riders.services.RiderDispatcherService.notify_rider_pickup_ready")
    @patch("apps.riders.services.RiderDispatcherService.notify_rider_delivery_offer")
    def test_rider_accepts_active_offer_and_becomes_assigned(self, notify_offer, notify_ready):
        rider = self.create_available_rider()
        order = self.create_order(status=OrderStatus.PREPARING)
        RiderDispatcherService.offer_order_to_best_rider(order)

        accepted, message = RiderDispatcherService.accept_order_offer(order, rider.user)

        self.assertTrue(accepted, message)
        order.refresh_from_db()
        rider.refresh_from_db()
        offer = RiderOrderOffer.objects.get(order=order, rider=rider)
        self.assertEqual(order.rider_id, rider.user_id)
        self.assertFalse(rider.is_available)
        self.assertEqual(offer.status, RiderOrderOfferStatus.ACCEPTED)
        notify_ready.assert_called_once_with(order)

    @patch("apps.riders.services.RiderDispatcherService.notify_rider_delivery_offer")
    def test_wrong_rider_cannot_accept_offer(self, notify_offer):
        self.create_available_rider()
        other_rider = RiderProfile.objects.create(
            user=self.other_rider_user,
            is_online=True,
            is_available=True,
            can_do_delivery=True,
            current_latitude=7.190900,
            current_longitude=125.455500,
        )
        order = self.create_order(status=OrderStatus.PREPARING)
        RiderDispatcherService.offer_order_to_best_rider(order)

        accepted, message = RiderDispatcherService.accept_order_offer(order, other_rider.user)

        self.assertFalse(accepted)
        self.assertEqual(message, "No active delivery offer was found for this rider.")
        order.refresh_from_db()
        self.assertIsNone(order.rider_id)

    @patch("apps.riders.services.RiderDispatcherService.notify_rider_delivery_offer")
    def test_ready_dispatch_offers_nearest_rider_when_no_offer_exists(self, notify_offer):
        rider = self.create_available_rider()
        order = self.create_order(status=OrderStatus.READY)

        dispatched = RiderDispatcherService.dispatch_ready_order(order)

        self.assertTrue(dispatched)
        order.refresh_from_db()
        rider.refresh_from_db()
        offer = RiderOrderOffer.objects.get(order=order, rider=rider)
        self.assertIsNone(order.rider_id)
        self.assertTrue(rider.is_available)
        self.assertEqual(offer.status, RiderOrderOfferStatus.OFFERED)
        notify_offer.assert_called_once()

    def create_available_rider(self):
        return RiderProfile.objects.create(
            user=self.rider_user,
            is_online=True,
            is_available=True,
            can_do_delivery=True,
            current_latitude=7.190700,
            current_longitude=125.455300,
        )

    def create_order(self, status):
        order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            delivery_method=DeliveryMethod.DELIVERY,
            status=status,
            delivery_address_text="Customer address",
            delivery_latitude=Decimal("7.200000"),
            delivery_longitude=Decimal("125.460000"),
            subtotal=Decimal("100.00"),
            delivery_fee=Decimal("50.00"),
            system_fee=Decimal("10.00"),
            total_amount=Decimal("160.00"),
        )
        order.items.create(
            product=self.product,
            quantity=1,
            unit_price=self.product.price,
        )
        return order
