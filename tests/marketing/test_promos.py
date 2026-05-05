from django.test import TestCase

class PromoCodeTests(TestCase):
    def test_promo_minimum_spend(self):
        """
        Ensure a promo code cannot be applied if the order 
        subtotal is less than the minimum_spend requirement.
        """
        pass

    def test_promo_max_discount_cap(self):
        """
        Ensure a percentage-based promo (e.g., 50% off) respects 
        the max_discount_amount cap (e.g., max 100 PHP).
        """
        pass

    def test_promo_concurrency_limit(self):
        """
        Ensure atomic transaction and F() expression correctly 
        prevent usage_limit from being exceeded if 50 users apply 
        the code simultaneously.
        """
        pass
