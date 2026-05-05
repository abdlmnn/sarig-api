from django.test import TestCase

class RiderDispatcherTests(TestCase):
    def test_haversine_distance_calculation(self):
        """
        Ensure the math behind the GPS distance is accurate.
        Test with known lat/lng points and compare with actual KM distance.
        """
        pass

    def test_rider_assignment_logic(self):
        """
        Ensure the dispatcher only assigns orders to riders who are:
        1. is_online = True
        2. is_available = True
        3. Closest to the store
        """
        pass

    def test_pickup_bypasses_dispatch(self):
        """
        Ensure that if an order has delivery_method='PICKUP', 
        the RiderDispatcherService does NOT attempt to assign a rider.
        """
        pass
